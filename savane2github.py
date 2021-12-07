#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
savane2github.py - Savane to GitHub Migration Tool
Copyright 2021 Marius Greuel
Licensed under the GNU GPL v3.0
"""

import argparse
import json
from json import JSONEncoder
from json import JSONDecoder
import logging
import os
import requests
import sys
import bs4
from github import Github

class ItemType:
    def __init__(self, path, singular, plural):
        self.path = path
        self.singular = singular
        self.plural = plural

class TrackerComment:
    def __init__(self):
        self.author = None
        self.time = None
        self.text = None

    def __str__(self):
        text = ''
        if self.author: text += self.author + '\n'
        if self.time: text += self.time + '\n'
        if self.text: text += '\n' + self.text + '\n'
        return text.strip()

class TrackerAttachment:
    def __init__(self):
        self.text = None
        self.url = None

    def __str__(self):
        return '[' + self.text + '](' + self.url + ')'

class Tracker:
    def __init__(self):
        self.type = ''
        self.item_id = 0
        self.summary = None
        self.originator_name = None
        self.originator_email = None
        self.severity = None
        self.priority = None
        self.category_id = None
        self.status_id = None
        self.resolution_id = None
        self.assigned_to = None
        self.programmer_hardware = None
        self.device_type = None
        self.url = None
        self.description = None
        self.comments = []
        self.attachments = []

    def __str__(self):
        text = ''
        if self.summary: text += f'Summary: {self.summary}\n'
        if self.originator_name: text += f'Originator Name: {self.originator_name}\n'
        if self.originator_email: text += f'Originator Email: {self.originator_email}\n'
        if self.severity: text += f'Severity: {self.severity}\n'
        if self.priority: text += f'Priority: {self.priority}\n'
        if self.category_id: text += f'Category ID: {self.category_id}\n'
        if self.status_id: text += f'Status: {self.status_id}\n'
        if self.resolution_id: text += f'Status: {self.resolution_id}\n'
        if self.assigned_to: text += f'Assigned to: {self.assigned_to}\n'
        if self.programmer_hardware: text += f'Programmer hardware: {self.programmer_hardware}\n'
        if self.device_type: text += f'Device type: {self.device_type}\n'
        if self.description: text += f'\n{self.description.text}\n\n'

        for attachment in self.attachments:
            text += str(attachment) + '\n'

        return text.strip()

class IssueEncoder(JSONEncoder):
    def default(self, o):
        d = { '_json_type': type(o).__name__ }
        d.update(o.__dict__)
        return d

class IssueDecoder(JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, o):
        if '_json_type' not in o: return o
        x = globals()[o['_json_type']]()
        for k, v in o.items(): setattr(x, k, v)
        return x

def list_tracker(session, instance, project, tracker_type):
    logging.info(f"Browsing {tracker_type.plural} at '{instance}/projects/{project}'...")
    items = {}

    offset = 0
    chunk_size = 50
    while True:
        url = f'{instance}/{tracker_type.path}/?group={project}&func=browse&set=custom&status_id=0&offset={offset}&chunksz={chunk_size}#results'
        logging.debug(f"Loading page '{url}'...")
        soup = bs4.BeautifulSoup(session.get(url).text, features='lxml')

        table = soup.find('table', class_='box')
        if not table:
           break

        rows = table.find_all('tr')
        if len(rows) <= 1:
           break

        for row in rows:
            if row.td:
                a_summary = row.find_all('td')[1].a
                id = int(a_summary['href'][1:])
                items[id] = a_summary.string

        offset += chunk_size

    path = f'{project}/list_{tracker_type.plural}.json'
    logging.info(f"Writing '{path}'...")
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(items, file, sort_keys=True, indent=4)

def download_tracker(session, instance, project, tracker_type,):
    path = f'{project}/list_{tracker_type.plural}.json'
    logging.info(f"Reading '{path}'...")
    with open(path, 'r', encoding='utf-8') as file:
        items = json.load(file)

    logging.info(f"Downloading {tracker_type.plural} from '{instance}/projects/{project}'...")
    for id in items:
        path = f'{project}/page_{tracker_type.singular}_{id}.html'
        if os.path.isfile(path):
            logging.debug(f"Page '{path}' exists, skipping...")
        else:
            url = f'{instance}/{tracker_type.path}/?{id}'
            logging.info(f"Loading page '{url}'...")
            page = session.get(url).text
            logging.debug(f"Writing page '{path}'...")
            with open(path, 'w', encoding='utf-8') as file:
                file.write(page)

def import_tracker(instance, project, tracker_type):
    def parse_tracker(instance, tracker_type, text):
        def get_input_field(form, name):
            input = form.find('input', attrs={'name': name})
            return input['value'] if input else None

        def get_select_field(form, name):
            select = form.find('select', attrs={'name': name})
            selected = select.find('option', attrs={'selected': 'selected'}) if select else None
            return str(selected.string) if selected else None

        def html_to_markup(instance, contents):
            def has_left_whitespace(item):
                return len(item.string.lstrip()) < len(item.string)

            def has_right_whitespace(item):
                return len(item.string.rstrip()) < len(item.string)

            def element_to_markup(instance, contents):
                text = ''
                list_type = None
                separator = None
                for item in contents:
                    if type(item) is bs4.element.Tag:
                        if item.name == 'p':
                            text += element_to_markup(instance, item.contents).rstrip(' \t\xa0') + '\n'
                            separator = None
                        elif item.name == 'br':
                            text = text.rstrip(' \t\xa0') + '\n'
                            separator = None
                        elif item.name == 'hr':
                            separator = None
                        elif item.name == 'blockquote':
                            if 'verbatim' in item.get('class', []):
                                text += '```\n'
                                text += element_to_markup(instance, item.contents)
                                text += '```\n'
                            else:
                                text += element_to_markup(instance, item.contents)
                            separator = None
                        elif item.name == 'ul' or item.name == 'ol':
                            list_type = item.name
                            text += element_to_markup(instance, item.contents)
                            separator = None
                        elif item.name == 'li':
                            if list_type == 'ol':
                                text += '1. ' + element_to_markup(instance, item.contents)
                            else:
                                text += '- ' + element_to_markup(instance, item.contents)
                            separator = None
                        elif item.name == 'img':
                            text += '![' + item.get('alt', 'image') + '](' + item.get('src', '') + ')\n' + element_to_markup(instance, item.contents)
                            separator = None
                        elif item.name == 'a':
                            text += separator if separator else ''
                            text += '[' + element_to_markup(instance, item.contents) + '](' + instance + item.get('href', '#') + ')'
                            separator = ''
                        elif item.name == 'em' or item.name == 'strong':
                            text += separator if separator else ''
                            text += '**' + element_to_markup(instance, item.contents).strip() + '**'
                            separator = ''
                        else:
                            logging.warning(f"Unexpected element tag '{item.name}'")
                            text += element_to_markup(instance, item.contents)
                            separator = None
                    elif type(item) is bs4.element.NavigableString:
                        text += ' ' if separator == ' ' or separator == '' and has_left_whitespace(item) else ''
                        text += item.string.strip()
                        separator = ' ' if has_right_whitespace(item) else ''
                    elif type(item) is bs4.element.Comment:
                        pass
                    else:
                        logging.warning(f"Unexpected element type '{type(item)}'")
                        text += str(item).strip()
                        separator = None
                return text

            return element_to_markup(instance, contents).strip()

        soup = bs4.BeautifulSoup(text, features='lxml')
        form = soup.find('form', attrs={'name': 'item_form'})

        tracker = Tracker()
        tracker.type = tracker_type.singular
        tracker.item_id = int(get_input_field(form, 'item_id'))
        tracker.summary = get_input_field(form, 'summary')
        tracker.originator_name = get_input_field(form, 'originator_name')
        tracker.originator_email = get_input_field(form, 'originator_email')
        tracker.severity = get_select_field(form, 'severity')
        tracker.priority = get_select_field(form, 'priority')
        tracker.category_id = get_select_field(form, 'category_id')
        tracker.status_id = get_select_field(form, 'status_id')
        tracker.resolution_id = get_select_field(form, 'resolution_id')
        tracker.assigned_to = get_select_field(form, 'assigned_to')
        tracker.programmer_hardware = get_input_field(form, 'custom_tf1')
        tracker.device_type = get_input_field(form, 'custom_tf2')
        tracker.url = f'{instance}/{tracker_type.path}/?{tracker.item_id}'

        comments = soup.find('div', id='hidsubpartcontentdiscussion')
        if comments:
            for row in comments.table.find_all('tr'):
                tracker_comment = row.find('div', class_='tracker_comment')
                if tracker_comment:
                    cols = row.find_all('td')
                    comment = TrackerComment()
                    comment.author = cols[1].a.string
                    comment.time = str(cols[0].a.contents)[2:].split(',')[0]
                    comment.text = html_to_markup(instance, tracker_comment.contents).strip()
                    tracker.comments.insert(0, comment)

            if len(tracker.comments) > 0:
                tracker.description = tracker.comments.pop(0)

        attachments = soup.find('div', id='hidsubpartcontentattached')
        if attachments:
            for a in attachments.find_all('a'):
                if str(a).find('<!-- file -->') > 0:
                    attachment = TrackerAttachment()
                    attachment.text = html_to_markup(instance, a.contents)
                    attachment.url = instance + a.get('href', '#')
                    tracker.attachments.insert(0, attachment)

        return tracker

    path = f'{project}/list_{tracker_type.plural}.json'
    logging.info(f"Reading '{path}'...")
    with open(path, 'r', encoding='utf-8') as file:
        items = json.load(file)

    trackers = []

    for id in items:
        path = f'{project}/page_{tracker_type.singular}_{id}.html'
        if not os.path.isfile(path):
            logging.warning(f"Page '{path}' missing, skipping...")
        else:
            logging.info(f"Reading page '{path}'...")
            with open(path, 'r', encoding='utf-8') as file:
                trackers.append(parse_tracker(instance, tracker_type, file.read()))

    path = f'{project}/trackers_{tracker_type.plural}.json'
    logging.info(f"Writing '{path}'...")
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(trackers, file, indent=4, cls=IssueEncoder)

def dump_tracker(project, tracker_type):
    path = f'{project}/trackers_{tracker_type.plural}.json'
    logging.info(f"Reading '{path}'...")
    with open(path, 'r', encoding='utf-8') as file:
        trackers = json.load(file, cls=IssueDecoder)

    for tracker in trackers:
        print('======')
        print(tracker)
        for comment in tracker.comments:
            print('------')
            print(comment)

def export_tracker(project, repo_path, access_token, dry_run, tracker_type):
    path = f'{project}/trackers_{tracker_type.plural}.json'
    logging.info(f"Reading '{path}'...")
    with open(path, 'r', encoding='utf-8') as file:
        trackers = json.load(file, cls=IssueDecoder)

    if not dry_run:
        logging.info(f"Creating GitHub instance...")
        g = Github(access_token)
        repo = g.get_repo(repo_path)
        labels = ['bug', 'question', 'wontfix', 'invalid', 'duplicate']
        repo_labels = dict(zip(labels, map(repo.get_label, labels)))

    for tracker in trackers:
        issue_title = f'[{tracker.type} #{tracker.item_id}] {tracker.summary}'

        issue_body = ''
        if tracker.originator_name: issue_body += f'{tracker.originator_name} <{tracker.originator_email}>\n'
        if tracker.description: issue_body += f'{tracker.description.time}\n'
        if tracker.programmer_hardware: issue_body += f'Programmer hardware: {tracker.programmer_hardware}\n'
        if tracker.device_type: issue_body += f'Device type: {tracker.device_type}\n'
        issue_body += f'\n{tracker.description.text}\n'

        if len(tracker.attachments) > 0:
            issue_body += '\n'
            for attachment in tracker.attachments:
                issue_body += str(attachment) + '\n'

        issue_body += f'\nThis issue was migrated from {tracker.url}'

        print('======')
        print(issue_title)
        print('======')
        print(issue_body)

        issue_labels = []
        if tracker.resolution_id == 'Need Info':
            issue_labels.append('question')
        if tracker.resolution_id == 'Confirmed' or tracker.resolution_id == 'Fixed' or tracker.resolution_id == 'In Progress':
            issue_labels.append('bug')
        if tracker.resolution_id == 'Wont Fix':
            issue_labels.append('wontfix')
        if tracker.resolution_id == 'Works For Me' or tracker.resolution_id == 'Invalid':
            issue_labels.append('invalid')
        if tracker.resolution_id == 'Duplicate':
            issue_labels.append('duplicate')

        print('!Labels', issue_labels)

        if not dry_run:
            issue = repo.create_issue(title=issue_title, body=issue_body, labels=[repo_labels[label] for label in issue_labels])

        for comment in tracker.comments:
            print('------')
            print(comment)
            if not dry_run:
                issue.create_comment(str(comment))

        if tracker.status_id == 'Closed':
            print('!Closed')
            if not dry_run:
                issue.edit(state='closed')

def main():
    def parse_commandline():
        parser = argparse.ArgumentParser()
        parser.add_argument('--instance', default='https://savannah.nongnu.org', help='URL to Savane server instance (default https://savannah.nongnu.org)')
        parser.add_argument('--project', help='Name of the Savane project')
        parser.add_argument('--username', help='Username for HTTP authentication')
        parser.add_argument('--password', help='Password for HTTP authentication')
        parser.add_argument('--repo-path', help='The full name or id of the GitHub repo such as \'user/name\'')
        parser.add_argument('--access-token', help='The GitHub access token used to create the issues')
        parser.add_argument('--list-bugs', action='store_true', help='Create JSON list of bugs')
        parser.add_argument('--list-tasks', action='store_true', help='Create JSON list of tasks')
        parser.add_argument('--list-patches', action='store_true', help='Create JSON list of patches')
        parser.add_argument('--download-bugs', action='store_true', help='Download HTML bug pages')
        parser.add_argument('--download-tasks', action='store_true', help='Download HTML task pages')
        parser.add_argument('--download-patches', action='store_true', help='Download HTML patch pages')
        parser.add_argument('--import-bugs', action='store_true', help='Create JSON tracker file from the downloaded bug pages')
        parser.add_argument('--import-tasks', action='store_true', help='Create JSON tracker file from the downloaded task pages')
        parser.add_argument('--import-patches', action='store_true', help='Create JSON tracker file from the downloaded patch pages')
        parser.add_argument('--dump-bugs', action='store_true', help='Dump bugs JSON tracker file')
        parser.add_argument('--dump-tasks', action='store_true', help='Dump tasks JSON tracker file')
        parser.add_argument('--dump-patches', action='store_true', help='Dump patches JSON tracker file')
        parser.add_argument('--export-bugs', action='store_true', help='Export bugs to GitHub')
        parser.add_argument('--export-tasks', action='store_true', help='Export tasks to GitHub')
        parser.add_argument('--export-patches', action='store_true', help='Export patches to GitHub')
        parser.add_argument('--dry-run', action='store_true', help='Do not make actual changes to GitHub')
        parser.add_argument('-v', '--verbose', action='store_const', dest='loglevel', default=logging.INFO, const=logging.DEBUG, help='enable verbose command-line output')
        args = parser.parse_args()

        valid = False
        valid |= args.list_bugs and args.project != None
        valid |= args.list_tasks and args.project != None
        valid |= args.list_patches and args.project != None
        valid |= args.download_bugs and args.project != None
        valid |= args.download_tasks and args.project != None
        valid |= args.download_patches and args.project != None
        valid |= args.import_bugs and args.project != None
        valid |= args.import_tasks and args.project != None
        valid |= args.import_patches and args.project != None
        valid |= args.dump_bugs and args.project != None
        valid |= args.dump_tasks and args.project != None
        valid |= args.dump_patches and args.project != None
        valid |= args.export_bugs and args.project != None and args.repo_path != None and args.access_token != None
        valid |= args.export_tasks and args.project != None and args.repo_path != None and args.access_token != None
        valid |= args.export_patches and args.project != None and args.repo_path != None and args.access_token != None

        if not valid:
            parser.print_help()
            exit(2)

        return args

    def setup_logger(loglevel):
        logging.basicConfig(format='%(levelname)s: %(message)s', level=loglevel)

    def authenticate_session(session, instance, project, username, password):
        if username and password:
            logging.info(f"Authenticating at '{instance}' as '{username}'...")
            form = { 'login': 'Login', 'uri': f'/projects/{project}/', 'form_loginname': username, 'form_pw': password, 'stay_in_ssl': '1', 'cookie_for_a_year': '1', 'brotherhood': '0' }
            response = session.post(f'{instance}/account/login.php', data=form)

    print('Savane to GitHub Migration Tool v1.0', file=sys.stderr)
    print('Copyright (C) 2021 Marius Greuel', file=sys.stderr)
    args = parse_commandline()
    setup_logger(args.loglevel)

    try:
        os.makedirs(args.project, exist_ok=True)
        with requests.Session() as session:
            what = {
                'bug': ItemType('bugs', 'bug', 'bugs'),
                'task': ItemType('task', 'task', 'tasks'),
                'patch': ItemType('patch', 'patch', 'patches')
            }

            authenticate_session(session, args.instance, args.project, args.username, args.password)

            if args.list_bugs:
                list_tracker(session, args.instance, args.project, what['bug'])
            if args.list_tasks:
                list_tracker(session, args.instance, args.project, what['task'])
            if args.list_patches:
                list_tracker(session, args.instance, args.project, what['patch'])
            if args.download_bugs:
                download_tracker(session, args.instance, args.project, what['bug'])
            if args.download_tasks:
                download_tracker(session, args.instance, args.project, what['task'])
            if args.download_patches:
                download_tracker(session, args.instance, args.project, what['patch'])
            if args.import_bugs:
                import_tracker(args.instance, args.project, what['bug'])
            if args.import_tasks:
                import_tracker(args.instance, args.project, what['task'])
            if args.import_patches:
                import_tracker(args.instance, args.project, what['patch'])
            if args.dump_bugs:
                dump_tracker(args.project, what['bug'])
            if args.dump_tasks:
                dump_tracker(args.project, what['task'])
            if args.dump_patches:
                dump_tracker(args.project, what['patch'])
            if args.export_bugs:
                export_tracker(args.project, args.repo_path, args.access_token, args.dry_run, what['bug'])
            if args.export_tasks:
                export_tracker(args.project, args.repo_path, args.access_token, args.dry_run, what['task'])
            if args.export_patches:
                export_tracker(args.project, args.repo_path, args.access_token, args.dry_run, what['patch'])

        exit(0)
    except SystemExit:
        raise
    except:
        logging.critical(f'Exception caught: {sys.exc_info()}')
        raise

if __name__ == '__main__':
    main()
