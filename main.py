#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Linggar Primahastoko
# Email: x@linggar.asia

from flask import Flask, render_template, session, request, redirect,  url_for
from flask_socketio import SocketIO, Namespace, emit, disconnect, join_room, rooms, leave_room, close_room

async_mode = None

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = "s3cr3t!"

socketio = SocketIO(app, async_mode=async_mode)
clients = []
users = {}
room_lists = {}
all_chat = {}

thread = None
def background_thread():
	count = 0
	while True:
		socketio.sleep(10)
		count += 1

def get_username(sid):
	# Get Username By Request Sid
	for user in users:
		if users[user] == sid:
			return user
	return False

@app.route('/')
def index():
	exists = request.args.get('exists', 0)
	return render_template('index.html', exists=exists)

@app.route('/check/<string:username>')
def user_check(username):
	# Check if username is exist
	if username in users:
		return '1'
	return '0'

@app.route('/check/room/<string:room_name>')
def room_check(room_name):
	# Check if room is exist
	if room_name in room_lists:
		return '1'
	return '0'

@app.route('/<string:username>')
def main_chat(username):
	return render_template('chat.html', async_mode=socketio.async_mode)

class WebChat(Namespace):
	def on_connect(self):
		global thread
		clients.append(request.sid)
		if thread is None:
			thread = socketio.start_background_task(target=background_thread)

	def on_register(self, message):
		# Register user to the lists
		users[message['user']] = request.sid

		# Append user to object, so we know the chat state between two users
		all_chat[message['user']] = []

		# Broadcast that there is user is connected
		emit('user_response', {
				'type': 'connect',
				'message': '{0} is connected to the server'.format(message['user']),
				'data': {
					'users': users,
					'rooms': room_lists,
				},
			}, broadcast=True)

	def on_private_message(self, message):
		user = get_username(request.sid)
		# if there is no chat state between two users, append to the object
		if message['user'] not in all_chat[user]:
			emit('message_response', {
					'type': 'private',
					'message': '',
					'data': {
						'user': message['user'],
					},
				})
			all_chat[user].append(message['user'])

	def on_private_send(self, message):
		user = get_username(request.sid)
		# if there is no chat state between two users, open new chat
		if user not in all_chat[message['friend']]:
			all_chat[message['friend']].append(user)
			emit('message_response', {
					'type': 'new_private',
					'message': '',
					'data': {
						'user': user
					}
				}, room=users[message['friend']])

		# send the message to the other
		private_act = 'pm'

		# if type is disconnect, will send all disconnected user message
		if 'act' in message:
			private_act = 'disconnect'
		emit('message_response', {
				'type': 'private_message',
				'act': private_act,
				'data': {
					'text': message['text'],
					'from': user,
				}
			}, room=users[message['friend']])	
		

	def on_room_send(self, message):
		user = get_username(request.sid)

		# because room id from the html start with rooms_ then get room name
		temp_room_name = message['friend'].split('_')
		room_name = '_'.join(temp_room_name[1:len(temp_room_name)])
		emit('message_response', {
				'type': 'room_message',
				'data': {
					'text': message['text'],
					'room': room_name,
					'from': user,
				}
			}, room=room_name)

	def on_close_chat(self, message):
		user = get_username(request.sid)
		if message['user'] in all_chat[user]:
			emit('message_response', {
					'type': 'private_close',
					'message': '',
					'data': {
						'user': message['user']
					}
				})
			all_chat[user].remove(message['user'])

	def on_create_room(self, message):
		# If the room is not exist, append new room to rooms object, also set the admin and initial user
		if message['room'] not in room_lists:
			room_lists[message['room']] = {}
			user = get_username(request.sid)
			room_lists[message['room']]['admin'] = user
			room_lists[message['room']]['users'] = [user]
			join_room(message['room'])
			emit('feed_response', {
					'type': 'rooms',
					'message': '{0} created room {1}'.format(room_lists[message['room']]['admin'], message['room']),
					'data': room_lists
				}, broadcast=True)

			emit('message_response', {
					'type': 'open_room',
					'data': {
						'room': message['room'],
					},
				})
		else:
			emit('feed_response', {
					'type': 'feed',
					'message': 'Room is exist, please use another room',
					'data': False,
				})
	
	def on_get_room_users(self, message):
		if message['room'] in room_lists:
			emit('feed_response', {
					'type': 'room_users',
					'message': '',
					'data': room_lists[message['room']]['users'],
					'rooms': room_lists,
				})

	def on_join_room(self, message):
		if message['room'] in room_lists:
			user = get_username(request.sid)
			if user in room_lists[message['room']]['users']:
				emit('feed_response', {
						'type': 'feed',
						'message': 'You have already joined the room',
						'data': False
					})
			else:
				# join room
				join_room(message['room'])
				# append to room users array
				room_lists[message['room']]['users'].append(user)

				# tell the existing users that there is new user joining the room
				emit('feed_response', {
						'type': 'new_joined_users',
						'message': '{0} joined room {1}'.format(user, message['room']),
						'data': room_lists[message['room']]['users'],
						'room': message['room'],
						'user_action': user,
						'welcome_message': '{0} join the room'.format(user),
					}, room=message['room'])

				# Append to news feed that there is user joining the room
				emit('feed_response', {
					'type': 'rooms',
					'message': '',
					'data': room_lists
				}, broadcast=True)

				# tell the frontend that this is the message for joining the room
				# open chat with id rooms_roomName
				emit('message_response', {
					'type': 'open_room',
					'data': {
						'room': message['room'],
					},
				})

	def on_close_room(self, message):
		user = get_username(request.sid)
		temp_room_name = message['room'].split('_')
		room_name = '_'.join(temp_room_name[1:len(temp_room_name)])

		# if admin, close the room
		if user == room_lists[room_name]['admin']:
			# broadcast to users in the room
			emit('message_response', {
				'type': 'room_feed',
				'data': {
					'text': '{0} (Admin) is closing the room'.format(user),
					'room': room_name,
					'from': user,
				}
			}, room=room_name)
			
			# update room user list
			emit('feed_response', {
				'type': 'update_room_users',
				'message': '',
				'data': room_lists[room_name]['users'],
				'room': room_name,
				'user_action': user,
				'act': 'close',
			}, broadcast=True)

			# close room
			close_room(room_name)
			# remove room from list
			room_lists.pop(room_name)

			# send message to feed
			emit('feed_response', {
				'type': 'rooms',
				'message': '{0} is closing room {1}'.format(user, room_name),
				'data': room_lists
			}, broadcast=True)
		else:
			# if not admin, leave room
			# broadcast to users in room
			emit('message_response', {
				'type': 'room_feed',
				'data': {
					'text': '{0} is leaving the room'.format(user),
					'room': room_name,
					'from': user,
				}
			}, room=room_name)

			# update room user list
			emit('feed_response', {
				'type': 'update_room_users',
				'message': '',
				'data': room_lists[room_name]['users'],
				'room': room_name,
				'user_action': user,
				'act': 'leave',
			}, room=room_name)

			# leave room
			leave_room(room_name)
			# remove user from room
			room_lists[room_name]['users'].remove(user)

			# broadcast to users in room that there is user leaving the room
			emit('feed_response', {
				'type': 'rooms',
				'message': '{0} is leaving room {1}'.format(user, room_name),
				'data': room_lists
			}, broadcast=True)

	def on_disconnect(self):
		if request.sid in clients:
			# remove sid from clients
			clients.remove(request.sid)
			user = get_username(request.sid)
			# if user is exist
			if user:
				all_rooms = [i for i in room_lists]		# create temporary array, so it won't affect the rooms list when it changes
				for room in all_rooms:
					# if user is admin in a room or user exist in a room, call close room function, logic handled by the function
					if room_lists[room]['admin'] == user or user in room_lists[room]['users']:
						self.on_close_room({
								'room': 'rooms_{0}'.format(room)
							})

				# broadcast to all chat friend that the user is disconnecting
				for friend in all_chat[user]:
					self.on_private_send({
							'friend': friend,
							'text': '{0} is offline'.format(user),
							'act': 'disconnect',
						})

				# remove user chat state
				all_chat.pop(user)

				# remove from users list
				users.pop(user)

				# append to news feed
				emit('user_response', {
					'type': 'connect',
					'message': '{0} is disconnected from the server'.format(user),
					'data': {
						'users': users,
						'rooms': room_lists,
					},
				}, broadcast=True)
				
		print 'Client disconnected {}'.format(request.sid)

	def on_my_ping(self):
		emit('my_pong')

socketio.on_namespace(WebChat('/chat'))

if __name__ == '__main__':
	socketio.run(app, debug=True, port=5000)