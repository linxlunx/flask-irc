# Flask IRC

Flask IRC is in memory websocket chat server using [Flask-SocketIO](https://flask-socketio.readthedocs.io/en/latest/). You can have group chat and private chat with Flask IRC.

## Run the server
```sh
$ pip install -r requirements.txt
$ python main.py
```

## Bugs And To Do Lists
- Integrate with database, so the application can handle the state if client refresh the browser.
- Handle duplicate username