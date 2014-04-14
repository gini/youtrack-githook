import re
import dateutil.parser
from flask import Flask, request, Response
from youtrack.connection import Connection
from youtrack import YouTrackException

# Configuration
YOUTRACK_URL = ''
YOUTRACK_USERNAME = ''
YOUTRACK_PASSWORD = ''
YOUTRACK_APIKEY = ''
REGEX = '([A-Z]+-\d+)'
DEFAULT_USER = ''

app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_pyfile('settings.cfg', silent=True)
app.config.from_envvar('GITHOOK_SETTINGS', silent=True)


# Application
@app.route('/')
def ping():
    return 'ping'

@app.route('/hook', methods=['POST'])
@app.route('/push_event', methods=['POST'])
def push_event_hook():
    push_event = request.json
    app.logger.debug(push_event)
    user_name = push_event['user_name']
    repo_name = push_event['repository']['name']
    repo_url = push_event['repository']['url']
    repo_homepage = push_event['repository']['homepage']
    refspec = push_event['ref']
    app.logger.debug('Received push event by %s in branch %s on repository %s', user_name, refspec, repo_url)

    for commit in push_event['commits']:
        app.logger.debug('Processing commit %s by %s (%s) in %s', commit['id'], commit['author']['name'], commit['author']['email'], commit['url'])
        commit_time = dateutil.parser.parse(commit['timestamp'])
        issues = re.findall(app.config['REGEX'], commit['message'], re.MULTILINE)
        if not issues:
            app.logger.debug('''Didn't find any referenced issues in commit %s''', commit['id'])
        else:
            app.logger.debug('Found %d referenced issues in commit %s', len(issues), commit['id'])
            yt = Connection(app.config['YOUTRACK_URL'], app.config['YOUTRACK_USERNAME'], app.config['YOUTRACK_PASSWORD'])

            default_user = yt.getUser(app.config['DEFAULT_USER'])
            user_login = default_user['login']

            users = yt.getUsers({ 'q': commit['author']['email'] })
            if not users:
                app.logger.warn('''Couldn't find user with email address %s. Using default user.''', commit['author']['email'])
            elif len(users) > 1:
                app.logger.warn('''Found more than one user with email address %s. Using default user.''', commit['author']['email'])
            else:
                user_login = users[0]['login']

            for issue_id in issues:
                app.logger.debug('Processing reference to issue %s', issue_id)
                try:
                    issue = yt.getIssue(issue_id)
                    comment_string = 'Commit [%(url)s %(id)s] on branch %(refspec)s in [%(repo_homepage)s %(repo_name)s] made by %(author)s on %(date)s\n{quote}%(message)s{quote}' % {'url': commit['url'], 'id': commit['id'], 'author': commit['author']['name'], 'date': str(commit_time), 'message': commit['message'], 'repo_homepage': repo_homepage, 'repo_name': repo_name, 'refspec': refspec}
                    app.logger.debug(comment_string)
                    yt.executeCommand(issueId=issue_id, command='comment', comment=comment_string.encode('utf-8'),
                                      run_as=user_login.encode('utf-8'))
                except YouTrackException:
                    app.logger.warn('''Couldn't find issue %s''', ref)
    return Response('Push event processed. Thanks!', mimetype='text/plain')


if __name__ == '__main__':
    app.run()
