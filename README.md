# discord-voicebot

A fully functional discord and telegram bot with various functions

# IMPORTANT!!!

The bot is configured to speak, learn and answer in Italian, if you want to configure it in another language, you will have to edit the code.

## Getting Started

These instructions will give you a copy of the project up and running on
your local or remote machine.

### Prerequisites

Automated install:
- systemd
- docker
- docker-compose

Manual install: 
- docker
- docker-compose

### Installing & Deploy

There are two ways to run this bot, one is by manually using docker-compose 
and another one is by using the convenience script install.sh.

The main difference is that the automated install requires systemd and will 
handle the bot restarts automatically.

- cp config.json.example to config.json and edit it with your params
- cp .env.sample to .env and edit it with your paarams
- cp one of the docker-compose(one of your choiche) file in the main dir to docker-compose.yml
- run "./install.sh" or docker-compose up
- if using the install.sh script you can use systemd to control the bot (systemctl start/stop/restart docker-compose@discord-voicebot)

### Bot Functions

TODO

