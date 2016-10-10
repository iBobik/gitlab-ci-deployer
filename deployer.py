#!/usr/bin/env python

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import gitlab
import os
import shutil
from io import BytesIO
import zipfile
from slugify import slugify
import re

HOST_NAME = ''
PORT_NUMBER = 8080
GITLAB_SERVER = 'https://gitlab.com'
TMP_PATH = '/tmp/deployer'

access_tokens = os.environ.get('GITLAB_WEBHOOK_TOKENS').split(',')
gl = gitlab.Gitlab(GITLAB_SERVER, os.environ.get('GITLAB_API_TOKEN'))

class WebhookHandler(BaseHTTPRequestHandler):
	def do_POST(self):
		if self.path == '/deployer':

			data_string = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
			data = json.loads(data_string)

			if data['object_kind'] == 'build' and data['build_status'] == 'success':
				project = gl.projects.get(data['project_id'])
				build = project.builds.get(data['build_id'])

				if not self.check_access(project):
					return

				self.do_build_success(data, project, build)
			else:
				self.send_response(200)
				self.end_headers()
				self.wfile.write(b"Not interested")

	def check_access(self, project):
		if self.headers['X-Gitlab-Token'] in access_tokens:
			return True

	# Process successful build
	def do_build_success(self, data, project, build):
		# Prepare tmp dir
		if os.path.exists(TMP_PATH):
			shutil.rmtree(TMP_PATH)
		os.makedirs(TMP_PATH)

		# Download and extract archive to tmp dir
		archive = BytesIO()
		archive.write(build.artifacts())
		archive = zipfile.ZipFile(archive)
		archive.extractall(TMP_PATH)

		# Build target dir
		format_data = {
			'unsafe_received_data': data,
			'project': project,
			'build': build,
			'slug_build_ref': slugify(build.ref, to_lower=True),
			'slug_project_name': slugify(project.name, to_lower=True)
		}
		target_dir = os.environ.get('TARGET_DIR').format(**format_data)

		# Move to target dir (and remove old)

		artifact_files = list(os.scandir(TMP_PATH))
		# No files
		if (len(artifact_files) == 0):
			print('Not deployed build #{0} because in artifacts are no files.'.format(build.id))
			self.send_response(500)
			return False

		# One item and is directory
		elif (len(artifact_files) == 1 and artifact_files[0].is_dir()):
			if os.path.exists(target_dir):
				shutil.rmtree(target_dir)
			shutil.move(artifact_files[0].path, target_dir)

		# Multiple items (files or directories)
		else:
			if os.path.exists(target_dir):
				shutil.rmtree(target_dir)
			shutil.move(TMP_PATH, target_dir)

		# Respond to client
		self.send_response(200)
		self.end_headers()
		self.wfile.write(b"Artifact deployed")
		print('Artifact deployed: ', target_dir)

		# Write note to merge request
		if os.environ.get('MERGE_REQUEST_NOTE') and os.environ.get('MERGE_REQUEST_NOTE_PREFIX'):
			self.do_write_note(project, build, format_data)

	# Add or update note to merge request
	def do_write_note(self, project, build, format_data):
		# Select MRs with the same branch
		for mr in project.mergerequests.list(state='opened'):
			if mr.source_branch != build.ref:
				continue

			# Find and replace note in current description or add it to the end
			prefix = os.environ.get('MERGE_REQUEST_NOTE_PREFIX')
			note = prefix + os.environ.get('MERGE_REQUEST_NOTE').format(**format_data)

			desc_replaced = re.subn(r'^' + re.escape(prefix) + '.*\n?', note + '\n', mr.description, flags=re.MULTILINE)
			if desc_replaced[1]: # Was something replaced
				if mr.description != desc_replaced[0]: # Is different
					mr.description = desc_replaced[0]
					mr.save()
			else: # Nothing replaced
				mr.description += '\n\n' + note
				mr.save()


if __name__ == '__main__':
	server_class = HTTPServer
	httpd = server_class((HOST_NAME, PORT_NUMBER), WebhookHandler)
	print("Server Starts - {}:{}".format(HOST_NAME, PORT_NUMBER))
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		pass
	httpd.server_close()
	print("Server Stops - {}:{}".format(HOST_NAME, PORT_NUMBER))
