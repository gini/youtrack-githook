"""
YouTrack 2.0 REST API
"""

import re
from xml.dom import Node
from xml.dom.minidom import Document
from xml.dom import minidom


EXISTING_FIELD_TYPES = {
    'numberInProject'   :   'integer',
    'summary'           :   'string',
    'description'       :   'string',
    'created'           :   'date',
    'updated'           :   'date',
    'updaterName'       :   'user[1]',
    'resolved'          :   'date',
    'reporterName'      :   'user[1]',
    'watcherName'       :   'user[*]',
    'voterName'         :   'user[*]'
}

EXISTING_FIELDS = ['numberInProject', 'projectShortName'] + EXISTING_FIELD_TYPES.keys()

class YouTrackException(Exception):
    def __init__(self, url, response, content):
        self.response = response
        self.content = content
        msg = 'Error for [' + url + "]: " + str(response.status)

        if response.reason is not None:
            msg += ": " + response.reason

        if response.has_key('content-type'):
            ct = response["content-type"]
            if ct is not None and ct.find('text/html') == -1:
                try:
                    xml = minidom.parseString(content)
                    self.error = YouTrackError(xml, self)
                    msg += ": " + self.error.error
                except:
                    self.error = content
                    msg += ": " + self.error

        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')

        Exception.__init__(self, msg)


class YouTrackObject(object):
    def __init__(self, xml=None, youtrack=None):
        self.youtrack = youtrack
        self._update(xml)

    def toXml(self):
        raise NotImplementedError

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        self._updateFromAttrs(xml)
        self._updateFromChildren(xml)

    def _updateFromAttrs(self, el):
        if el.attributes is not None:
            for i in range(el.attributes.length):
                a = el.attributes.item(i)
                setattr(self, a.name, a.value)

    def _updateFromChildren(self, el):
        children = [e for e in el.childNodes if e.nodeType == Node.ELEMENT_NODE]
        if (children):
            for c in children:
                name = c.getAttribute('name')
                if not len(name):
                    continue
                if isinstance(name, unicode):
                    name = name.encode('utf-8')
                values = c.getElementsByTagName('value')
                if (values is not None) and len(values):
                    if values.length == 1:
                        setattr(self, name, self._text(values.item(0)))
                    elif values.length > 1:
                        setattr(self, name, [self._text(value) for value in values])
                elif c.hasAttribute('value'):
                    value = c.getAttribute("value")
                    setattr(self, name, value)

    def _text(self, el):
        return "".join([e.data for e in el.childNodes if e.nodeType == Node.TEXT_NODE])

    def __repr__(self):
        _repr = ''
        for k, v in self.__dict__.items():
            if k == 'youtrack':
                continue
            if isinstance(k, unicode):
                k = k.encode('utf-8')
            if isinstance(v, unicode):
                v = v.encode('utf-8')
            _repr += k + ' = ' + str(v) + '\n'
        return _repr

    def __iter__(self):
        for item in self.__dict__:
            attr = self.__dict__[item]
            if isinstance(attr, basestring) or isinstance(attr, list) \
            or getattr(attr, '__iter__', False):
                yield item

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value


class YouTrackError(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if xml.documentElement.tagName == 'error':
            self.error = self._text(xml.documentElement)
        else:
            self.error = xml.toxml()


class Issue(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)
        if xml is not None:
            if len(xml.getElementsByTagName('links')) > 0:
                self.links = [Link(e, youtrack) for e in xml.getElementsByTagName('issueLink')]
            else:
                self.links = None

            if len(xml.getElementsByTagName('attachments')) > 0:
                self.attachments = [Attachment(e, youtrack) for e in xml.getElementsByTagName('fileUrl')]
            else:
                self.attachments = None
            for m in ['fixedVersion', 'affectsVersion']: self._normilizeMultiple(m)
            if hasattr(self, 'fixedInBuild') and (self.fixedInBuild == 'Next build'):
                self.fixedInBuild = None

    def _normilizeMultiple(self, name):
        if hasattr(self, name):
            attrValue = self[name]
            if not isinstance(attrValue, list):
                if isinstance(attrValue, unicode):
                    attrValue = attrValue.encode('utf-8')
                if attrValue is None or not len(attrValue):
                    delattr(self, name)
                else:
                    self[name] = [value.strip() for value in attrValue.split(',')]

    def getReporter(self):
        return self.youtrack.getUser(self.reporterName)

    def hasAssignee(self):
        return getattr(self, 'assigneeName', None) is not None

    def getAssignee(self):
        return self.youtrack.getUser(self.assigneeName)

    def getUpdater(self):
        return self.youtrack.getUser(self.updaterName)

    def hasVoters(self):
        return getattr(self, 'voterName', None) is not None

    def getVoters(self):
        voters = self.voterName
        if voters:
            if isinstance(voters, list):
                voters = [self.youtrack.getUser(v) for v in voters]
            else:
                voters = [self.youtrack.getUser(voters)]
        return voters

    def getComments(self):
        #TODO: do not make rest request if issue was initied with comments
        if not hasattr(self, 'comments'):
            setattr(self, 'comments', self.youtrack.getComments(self.id))
        return self.comments

    def getAttachments(self):
        if getattr(self, 'attachments', None) is None:
            return self.youtrack.getAttachments(self.id)
        else:
            return self.attachments

    def getLinks(self, outwardOnly=False):
        if getattr(self, 'links', None) is None:
            return self.youtrack.getLinks(self.id, outwardOnly)
        else:
            return [l for l in self.links if l.source == self.id or not outwardOnly]


class Comment(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

    def getAuthor(self):
        return self.youtrack.getUser(self.author)


class IssueChange(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        self.fields = []
        self.updated = 0
        self.updater_name = None
        self.comments = []
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        for field in xml.getElementsByTagName('field'):
            name = field.getAttribute('name')
            if name == 'updated':
                self.updated = int(self._text(field.getElementsByTagName('value')[0]))
            elif name == 'updaterName':
                self.updater_name = self._text(field.getElementsByTagName('value')[0])
            elif name == 'links':
                pass
            else:
                self.fields.append(ChangeField(field, self.youtrack))

        for comment in xml.getElementsByTagName('comment'):
            self.comments.append(comment.getAttribute('text'))


class ChangeField(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        self.name = None
        self.old_value = []
        self.new_value = []
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        self.name = xml.getAttribute('name')
        old_value = xml.getElementsByTagName('oldValue')
        for value in old_value:
            self.old_value.append(self._text(value))
        new_value = xml.getElementsByTagName('newValue')
        for value in new_value:
            self.new_value.append(self._text(value))

class Link(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

    def __hash__(self):
        return hash((self.typeName, self.source, self.target))

    def __eq__(self, other):
        return isinstance(other, Link) and self.typeName == other.typeName and self.source == other.source and self.target == other.target

    def __ne__(self, other):
        return not self.__eq__(other)

class Attachment(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)
        # Workaround for JT-18936
        self.url = re.sub(r'^.*?(?=/_persistent)', '', self.url)

    def getContent(self):
        return self.youtrack.getAttachmentContent(self.url.encode('utf-8'))

    def getAuthor(self):
        if self.authorLogin == '<no user>':
            return None
        return self.youtrack.getUser(self.authorLogin)


class User(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)
        self.getGroups = lambda : []

    def __hash__(self):
        return hash(self.login)

    def __cmp__(self, other):
        if isinstance(other, User):
            return cmp(self.login, other.login)
        else:
            return cmp(self.login, other)


class Group(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)


class Role(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

class UserRole(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        self.name = ''
        self.projects = []
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        self.name = xml.getAttribute("name")
        projects = xml.getElementsByTagName("projectRef")
        self.projects = [p.getAttribute("id") for p in projects] if projects is not None else []

    def toXml(self):
        result = '<userRole name="%s">' % self.name.encode('utf-8')
        if len(self.projects):
            result += '<projects>'
            result += "".join('<projectRef id="%s" url="dirty_hack"/>' % project.encode('utf-8') for project in self.projects)
            result += '</projects>'
        else:
            result += '<projects/>'
        result += '</userRole>'
        return result

class Permission(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

class Project(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)
        if not hasattr(self, 'description'):
            self.description = ''

    def getSubsystems(self):
        return self.youtrack.getSubsystems(self.id)

    def createSubsystem(self, name, isDefault, defaultAssigneeLogin):
        return self.youtrack.createSubsystem(self.id, name, isDefault, defaultAssigneeLogin)


class Subsystem(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)


class Version(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)
        if not hasattr(self, 'description'):
            self.description = ''

        if not hasattr(self, 'releaseDate'):
            self.releaseDate = None


class IssueLinkType(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)


class WorkItem(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        self.url = xml.getAttribute('url')
        for e in xml.childNodes:
            if e.tagName == 'author':
                self.authorLogin = e.getAttribute('login')
            else:
                self[e.tagName] = self._text(e)
    

class CustomField(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)


class ProjectCustomField(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        YouTrackObject.__init__(self, xml, youtrack)

    def _updateFromChildren(self, el):
        self.params = {}
        for c in el.getElementsByTagName('param'):
            name = c.getAttribute('name')
            value = c.getAttribute('value')
            self[name] = value
            self.params[name] = value


class UserBundle(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        self.users = []
        self.groups = []
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        self.name = xml.getAttribute("name")
        users = xml.getElementsByTagName("user")
        if users is not None:
            self.users = [self.youtrack.getUser(v.getAttribute("login")) for v in users]
        else:
            self.users = []
        groups = xml.getElementsByTagName("userGroup")
        if groups is not None:
            self.groups = [self.youtrack.getGroup(v.getAttribute("name")) for v in groups]
        else:
            self.groups = []

    def toXml(self):
        result = '<userBundle name="%s">' % self.name.encode('utf-8')
        result += "".join(
            '<userGroup name="%s" url="dirty_hack"></userGroup>' % group.name.encode('utf-8') for group in self.groups)
        result += "".join(
            '<user login="%s" url="yet_another_dirty_hack"></user>' % user.login.encode('utf-8') for user in self.users)
        result += '</userBundle>'
        return result

    def get_field_type(self):
        return "user"

    def get_all_users(self):
        all_users = self.users
        for group in self.groups:
            #returns objects containing only login and url info
            group_users = self.youtrack.getUsers({'group': group.name.encode('utf-8')})
            for user in group_users:
                # re-request credentials separately for each user to get more details
                try:
                    refined_user = self.youtrack.getUser(user.login)
                    all_users.append(refined_user)
                except YouTrackException, e:
                    print "Error on extracting user info for [" + str(user.login) + "] user won't be imported"
                    print e
        return list(set(all_users))


class Bundle(YouTrackObject):
    def __init__(self, element_tag_name, bundle_tag_name, xml=None, youtrack=None):
        self._element_tag_name = element_tag_name
        self._bundle_tag_name = bundle_tag_name
        self.values = []
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        self.name = xml.getAttribute("name")
        values = xml.getElementsByTagName(self._element_tag_name)
        if values is not None:
            self.values = [self._createElement(value) for value in values]
        else:
            self.values = []

    def toXml(self):
        result = '<%s name="%s">' % (self._bundle_tag_name, self.name.encode('utf-8'))
        result += ''.join(v.toXml() for v in self.values)
        result += '</%s>' % self._bundle_tag_name
        return result

    def get_field_type(self):
        return self._element_tag_name

    def createElement(self, name):
        element = self._createElement(None)
        element.name = name
        return element

    def _createElement(self, xml):
        pass


class BundleElement(YouTrackObject):
    def __init__(self, element_tag_name, xml=None, youtrack=None):
        self.element_name = element_tag_name
        YouTrackObject.__init__(self, xml, youtrack)

    def toXml(self):
        result = '<' + self.element_name
        for elem in self:
            if elem in ("name", "element_name"):
                continue
            value = self[elem]
            if value is None or not len(value):
                continue
            if isinstance(elem, unicode):
                elem = elem.encode('utf-8')
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            result += ' %s="%s"' % (elem, str(value))
        result += ">%s</%s>" % (self.name.encode('utf-8'), self.element_name)
        return result

    def _update(self, xml):
        if xml is None:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement

        self.name = [e.data for e in xml.childNodes if e.nodeType == Node.TEXT_NODE][0]
        self.description = xml.getAttribute('description')
        self.colorIndex = xml.getAttribute('colorIndex')
        self._update_specific_attributes(xml)

    def _update_specific_attributes(self, xml):
        pass


class EnumBundle(Bundle):
    def __init__(self, xml=None, youtrack=None):
        Bundle.__init__(self, "value", "enumeration", xml, youtrack)

    def _createElement(self, xml):
        return EnumField(xml, self.youtrack)

    def get_field_type(self):
        return "enum"


class EnumField(BundleElement):
    def __init__(self, xml=None, youtrack=None):
        BundleElement.__init__(self, "value", xml, youtrack)


class BuildBundle(Bundle):
    def __init__(self, xml=None, youtrack=None):
        Bundle.__init__(self, "build", "buildBundle", xml, youtrack)

    def _createElement(self, xml):
        return Build(xml, self.youtrack)


class Build(BundleElement):
    def __init__(self, xml=None, youtrack=None):
        BundleElement.__init__(self, "build", xml, youtrack)

    def _update_specific_attributes(self, xml):
        self.assembleDate = xml.getAttribute('assembleName')


class OwnedFieldBundle(Bundle):
    def __init__(self, xml=None, youtrack=None):
        Bundle.__init__(self, "ownedField", "ownedFieldBundle", xml, youtrack)

    def _createElement(self, xml):
        return OwnedField(xml, self.youtrack)


class OwnedField(BundleElement):
    def __init__(self, xml=None, youtrack=None):
        BundleElement.__init__(self, "ownedField", xml, youtrack)

    def _update_specific_attributes(self, xml):
        owner = xml.getAttribute("owner")
        if owner != '<no user>':
            self.owner = owner
        else:
            self.owner = None


class StateBundle(Bundle):
    def __init__(self, xml=None, youtrack=None):
        Bundle.__init__(self, "state", "stateBundle", xml, youtrack)

    def _createElement(self, xml):
        return StateField(xml, self.youtrack)


class StateField(BundleElement):
    def __init__(self, xml=None, youtrack=None):
        BundleElement.__init__(self, "state", xml, youtrack)

    def _update_specific_attributes(self, xml):
        self.is_resolved = xml.getAttribute("isResolved")


class VersionBundle(Bundle):
    def __init__(self, xml=None, youtrack=None):
        Bundle.__init__(self, "version", "versions", xml, youtrack)

    def _createElement(self, xml):
        return VersionField(xml, self.youtrack)


class VersionField(BundleElement):
    def __init__(self, xml=None, youtrack=None):
        BundleElement.__init__(self, "version", xml, youtrack)

    def _update_specific_attributes(self, xml):
        self.releaseDate = xml.getAttribute("releaseDate")
        self.released = xml.getAttribute("released").lower() == "true"
        self.archived = xml.getAttribute("archived").lower() == "true"


class IntelliSense(YouTrackObject):
    def __init__(self, xml=None, youtrack=None):
        self.suggestions = []
        self.highlights = []
        self.queries = []
        YouTrackObject.__init__(self, xml, youtrack)

    def _update(self, xml):
        if not xml:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement
        for c in xml.childNodes:
            if c.tagName in ('suggest', 'recent'):
                for item in c.getElementsByTagName('item'):
                    suggest = {}
                    for i in item.childNodes:
                        if i.tagName in ('completion', 'match'):
                            suggest[i.tagName] = {
                                'start': int(i.getAttribute('start')),
                                'end': int(i.getAttribute('end'))}
                        else:
                            if i.tagName == 'caret':
                                suggest[i.tagName] = int(self._text(i))
                            else:
                                suggest[i.tagName] = self._text(i)
                    if 'option' not in suggest:
                        continue
                    if c.tagName == 'suggest':
                        self.suggestions.append(suggest)
                    else:
                        self.queries.append(suggest)
            elif c.tagName == 'highlight':
                for item in c.getElementsByTagName('range'):
                    rng = {}
                    for i in item.childNodes:
                        if i.tagName in ('start', 'end'):
                            rng[i.tagName] = int(self._text(i))
                        else:
                            rng[i.tagName] = self._text(i)
                    self.highlights.append(rng)


class GlobalTimeTrackingSettings(YouTrackObject):
    def _update(self, xml):
        if not xml:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement
        for e in xml.childNodes:
            self[e.tagName] = self._text(e)


class ProjectTimeTrackingSettings(YouTrackObject):
    def _update(self, xml):
        if not xml:
            return
        if isinstance(xml, Document):
            xml = xml.documentElement
        self['Enabled'] = xml.getAttribute('enabled').lower() == 'true'
        self['EstimateField'] = None
        self['TimeSpentField'] = None
        for e in xml.childNodes:
            if e.tagName.lower() == 'estimation':
                self['EstimateField'] = e.getAttribute('name')
            elif e.tagName.lower() == 'spenttime':
                self['TimeSpentField'] = e.getAttribute('name')
