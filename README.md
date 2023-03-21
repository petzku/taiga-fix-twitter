# Discord twitter -> fxtwitter bot

Updates peoples' twitter links to fxtwitter, when the former fails to embed, or e.g. has video, in which case the built-in discord video player is often better than the twitter embed one.

## Usage

Runs on [discord.py](discord-py). [Virtualenv](venv) and [pip](pip) are recommended to manage library versions, in case other python applications run on the same machine.

### Initial setup

Install `virtualenv` and `pip`, and clone the project. Navigate to the repository directory, and run the following commands (assuming a bourne-like shell; usage of other shells is left as an exercise to the reader):
```sh
$ virtualenv venv           # or python3 -m venv venv
$ source venv/bin/activate  # on windows: venv\Scripts\activate.bat
$ pip3 install -r requirements.txt
```

Copy `config.py.sample` and rename it to `config.py`, then add your bot token into the file.

### Running the bot

Simply run the `main.py` script: 
```sh
$ python3 main.py
```

### Systemd

Alternatively, you can use the bundled systemd service file. Note that you will need to edit the `ExecStart` command to point to the location of your `daemon.sh` file.

[discord-py]: https://discordpy.readthedocs.io/en/stable/index.html
[pip]: https://pypi.org/project/pip/
[venv]: https://docs.python.org/3/tutorial/venv.html
