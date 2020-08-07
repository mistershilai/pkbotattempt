import pprint
import urllib.parse
from collections import namedtuple
from discord.ext import commands

from src import secret
from src.main import get_global_state


client = commands.Bot('.')


class SessionState:
    pass


Session = namedtuple('Session', 'context,command,session_state')


def html_to_discord(html_text):
    html_text = html_text.replace('<em>', '*').replace('<b>', '**').replace('<u>', '__').replace('<strong>', '**').replace('&lt;', '<')
    html_text = html_text.replace('</em>', '*').replace('</b>', '**').replace('</u>', '__').replace('</strong>', '**').replace('&gt;', '>')
    return html_text


@client.event
async def on_message(message):
    await client.process_commands(message)


@client.command()
async def reloadcogs(ctx):
    reload_extensions(client)


@client.command()
async def getloadedcogs(ctx):
    await ctx.send(code_block(pprint.pformat(client.extensions)))


def code_block(string):
    return '```' + string + '```'


def hyperlink(text, url):
    return '[' + text + ']' + '(' + url + ')'


def get_wikipedia_search(answer):
    return f'https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(answer)}'


def get_session(author, session_type):
    state = get_global_state()
    session = [session for session in state.sessions if session.context.author == author and isinstance(session.session_state, session_type)]
    assert len(session) < 2
    if len(session) == 0:
        return None
    return session[0]


extensions = ['pk_cog', 'tk_cog', 'tu_game_cog']

def load_extensions(bot):
    for ext in extensions:
        bot.load_extension(ext)


def unload_extensions(bot):
    for ext in extensions:
        bot.unload_extension(ext)


def reload_extensions(bot):
    for ext in extensions:
        bot.reload_extension(ext)


load_extensions(client)
client.run(secret.TOKEN)

