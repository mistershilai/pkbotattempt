import re
import traceback

import discord
from fuzzywuzzy import fuzz

from src.driver import SessionState, get_session, html_to_discord, Session, get_wikipedia_search, hyperlink
from discord.ext import commands

from src.main import get_global_state, get_db_connection, get_bonus_batch



SIMILARITY_RATIO_THRESHOLD = 70

class PkSessionState(SessionState):
    def __init__(self):
        self.bonuses = []
        self.bonus_parts_answered = 0
        self.bonuses_answered = 0
        self.points = 0
        self.current_bonus = None
        self.prompting = False


def setup(bot):
    bot.add_cog(PkCog(bot))


class PkCog(commands.Cog):
    @commands.command()
    async def pk(self, ctx, *args):
        state = get_global_state()
        state.skip_message = ctx.message
        if all([ctx.author != session.context.author for session in state.sessions]):
            new_session = Session(ctx, args, PkSessionState())
            state.sessions.append(new_session)
            await self.send_question(ctx.channel, new_session)
        else:
            await ctx.send(f'{ctx.author} is already in a pk')


    @commands.command()
    async def end(self, ctx, *args):
        state = get_global_state()
        state.skip_message = ctx.message

        # Don't end what a different cog is doing
        session = get_session(ctx.author, PkSessionState)
        if session is not None:
            await self.stats(ctx)
            state.sessions.remove(session)


    @commands.command()
    async def stats(self, ctx):
        get_global_state().skip_message = ctx.message
        session = get_session(ctx.author, PkSessionState)
        if session is not None:
            msg = discord.Embed(color=0xff0000, title='Stats', description=f'requested by {ctx.author.display_name}')
            msg.set_thumbnail(url=ctx.author.avatar_url)
            msg.add_field(name='Settings', value=str(session.command))
            msg.add_field(name='Bonuses', value=str(session.session_state.bonuses_answered) / 3)
            msg.add_field(name='Points', value=str(session.session_state.points))
            ppb = str(session.session_state.points / session.session_state.bonuses_answered) if session.session_state.bonuses_answered > 0 else 'N/A'
            msg.add_field(name='PPB', value=ppb)
            await ctx.send(embed=msg)


    async def send_question(self, channel, session):
        session_state = session.session_state

        if len(session_state.bonuses) <= 1:
            connection = get_db_connection()
            try:
                session_state.bonuses.extend(get_bonus_batch(connection, session.command))
            except Exception as e:
                await channel.send('Error: ' + str(e))
                await channel.send('Stacktrace' + str(traceback.print_tb(e.__traceback__)))
        if session_state.current_bonus is None or session_state.bonus_parts_answered == len(session_state.current_bonus[1]):
            try:
                session_state.current_bonus = session_state.bonuses.pop()
            except IndexError as e:
                await channel.send('Search returned 0 results -- ending pk')
                await self.end(session.context)
                return

            session_state.bonuses_answered += 1
            leadin_msg = discord.Embed(color=0x00ff00)
            leadin_msg.add_field(name=f'{session_state.current_bonus[2].name}', value=f'{html_to_discord(session_state.current_bonus[0].leadin)}')
            leadin_msg.set_author(name=f' for {session.context.author.display_name}', icon_url=session.context.author.avatar_url)
            await channel.send(embed=leadin_msg)
            session_state.bonus_parts_answered = 0

        bonus_part = discord.Embed(color=0x0000ff)
        bonus_part.add_field(name=str(session_state.bonus_parts_answered + 1), value=html_to_discord(session_state.current_bonus[1][session_state.bonus_parts_answered].formatted_text))
        bonus_part.set_author(name=f' for {session.context.author.display_name}',
                              icon_url=session.context.author.avatar_url)

        await channel.send(embed=bonus_part)

    @commands.Cog.listener()
    async def on_message(self, message):

        if get_global_state().skip_message is not None and message.id == get_global_state().skip_message.id:
            # skip it, it was used for a bot command
            return
        session = get_session(message.author, PkSessionState)
        if session is not None:
            if session.session_state.prompting:
                session.session_state.prompting = False
                if message.content.lower().startswith('y'):
                    session.session_state.points += 10
                session.session_state.bonus_parts_answered += 1
                await self.send_question(message.channel, session)
            else:
                # todo: get a better way to verify correct answers - how does pb do it?
                given_answer = message.content
                formatted_answer = session.session_state.current_bonus[1][
                    session.session_state.bonus_parts_answered].formatted_answer.lower().split('[')
                main_answer = html_to_discord(formatted_answer[0])
                unformatted_main_answer = main_answer.replace('*', '')
                correct_answers = re.findall(r'\*+.+?\*+', main_answer)
                if len(correct_answers) == 0:
                    correct_answers = [main_answer]
                if len(formatted_answer) > 1:
                    alternative_answer = html_to_discord(formatted_answer[1])
                    correct_answers = correct_answers + re.findall(r'\*+.+?\*+', alternative_answer)

                correct_answers = [a.lstrip().rstrip().lstrip('*').rstrip('*') for a in correct_answers]
                correct = False
                for ans in correct_answers:
                    correct = correct or fuzz.ratio(ans.lower(), given_answer.lower()) > SIMILARITY_RATIO_THRESHOLD

                if correct:
                    session.session_state.points += 10
                    session.session_state.bonus_parts_answered += 1
                    correct_msg = discord.Embed(color=0x0000ff)
                    wiki_search = hyperlink(html_to_discord("[".join(formatted_answer)), get_wikipedia_search(unformatted_main_answer))
                    correct_msg.add_field(name='Correct', value=wiki_search)
                    correct_msg.set_author(name=f' for {session.context.author.display_name}',
                                          icon_url=session.context.author.avatar_url)
                    await message.channel.send(embed=correct_msg)
                    await self.send_question(message.channel, session)
                else:
                    session.session_state.prompting = True
                    await message.channel.send(
                        f'DEBUG: correct_answers = {correct_answers}, similarities = {[fuzz.ratio(ans.lower(), given_answer.lower()) for ans in correct_answers]}')
                    incorrect_msg = discord.Embed(color=0xff0000)
                    wiki_search = hyperlink(html_to_discord("[".join(formatted_answer)),
                                            get_wikipedia_search(unformatted_main_answer))
                    incorrect_msg.add_field(name='Were you correct? [y/n]', value=wiki_search)
                    incorrect_msg.set_author(name=f' for {session.context.author.display_name}',
                                           icon_url=session.context.author.avatar_url)
                    await message.channel.send(embed=incorrect_msg)