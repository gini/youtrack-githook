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
def receive_hook():
    payload = request.json
    user_name = payload['user_name']
    repo_url = payload['repository']['url']
    app.logger.debug('Received payload for a push by %s on repository %s', user_name, repo_url)

    for commit in payload['commits']:
        app.logger.debug('Processing commit %s by %s (%s) in %s', commit['id'], commit['author']['name'], commit['author']['email'], commit['url'])
        commit_time = dateutil.parser.parse(commit['timestamp'])
        refs = re.findall(app.config['REGEX'], commit['message'], re.MULTILINE)
        if not refs:
            app.logger.info('''Didn't find any referenced issues in commit %s''', commit['id'])
        else:
            app.logger.info('Found %d referenced issues in commit %s', len(refs), commit['id'])

            yt = Connection(app.config['YOUTRACK_URL'], app.config['YOUTRACK_USERNAME'], app.config['YOUTRACK_PASSWORD'])

            user = app.config['DEFAULT_USER']
            users = yt.getUsers({ 'q': commit['author']['email'] })
            if not users:
                app.logger.warn('''Couldn't find user with email address %s. Using default user.''', commit['author']['email'])
            elif len(users) > 1:
                app.logger.warn('''Found more than one user with email address %s. Using default user.''', commit['author']['email'])
            else:
                user = users[0]['login']

            for ref in refs:
                app.logger.info('Processing reference to issue %s', ref)
                try:
                    issue = yt.getIssue(ref)
                    comment_string = 'Commit [%(url)s %(id)s] made by %(author)s on %(date)s\n{quote}%(message)s{quote}' % {'url': commit['url'], 'id': commit['id'], 'author': commit['author']['name'], 'date': str(commit_time), 'message': commit['message']}
                    app.logger.debug(comment_string)
                    yt.executeCommand(issueId=ref, command='comment', comment=comment_string.encode('utf-8'),
                                      run_as=user.encode('utf-8'))
                except YouTrackException:
                    app.logger.warn('''Couldn't find issue %s''', ref)
    return Response('Payload processed. Thanks!', mimetype='text/plain')


if __name__ == '__main__':
    app.run()
