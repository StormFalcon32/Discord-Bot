import random
import re

import discord
import gspread
from discord.ext import commands
from discord.utils import get
from oauth2client.service_account import ServiceAccountCredentials
from tabulate import tabulate

scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('sheetskey.json', scope)
sheets_client = gspread.authorize(creds)

sheet = sheets_client.open('Discord')
text_sheet = sheet.worksheet('Text')
teams_sheet = sheet.worksheet('Teams')
players_sheet = sheet.worksheet('Players')

client = commands.Bot(command_prefix='!')

started_draft = False
picked_caps = False
eligible_players = []
eligible_caps = []
draft_pool = []
caps_pool = []
draft_teams = [[], []]
current_team = 0

@client.command()
async def save_text(ctx, *args):
    author_id = str(ctx.message.author.id)
    save_data = ' '.join(args)
    all_data = text_sheet.get_all_values()[1:]
    ids = [row[0] for row in all_data]
    if author_id not in ids:
        text_sheet.append_row([author_id, save_data])
        await ctx.send('Added new user with text: {}'.format(save_data))
        return
    row = 2
    for user_id in ids:
        if user_id == author_id:
            text_sheet.update_cell(row, 2, save_data)
            break
        row += 1
    await ctx.send('Updated text to {}'.format(save_data))

@client.command()
async def get_text(ctx, *args):
    author_id = str(ctx.message.author.id)
    if args:
        author_id = args[0]
    all_data = text_sheet.get_all_values()[1:]
    ids = [row[0] for row in all_data]
    if author_id not in ids:
        await ctx.send('This user has not saved anything, did you get the right ID?')
        return
    row = 2
    for user_id in ids:
        if user_id == author_id:
            await ctx.send(all_data[row - 2][1])
            break
        row += 1

@client.command()
async def get_teams(ctx):
    teams = teams_sheet.get_all_values()
    await ctx.send('\n'.join([', '.join(row) for row in teams]))

@client.command()
async def start_draft(ctx):
    global started_draft
    global eligible_players
    global eligible_caps
    started_draft = True
    players = players_sheet.get_all_values()[1:]
    for row in players:
        if row[3] == '0':
            continue
        if row[4] == '1':
            eligible_caps.append(row[0])
        eligible_players.append(row[0])
    await ctx.send('Available Players: {}'.format(', '.join(eligible_players)))
    await ctx.send('Available Captains: {}'.format(', '.join(eligible_caps)))

@client.command()
async def end_draft(ctx):
    reset()
    await ctx.send('Draft ended')

@client.command()
async def random_caps(ctx):
    global picked_caps
    global draft_pool
    global caps_pool
    global draft_teams
    if not started_draft:
        await ctx.send('Need to do !start_draft first')
        return
    draft_teams = [[], []]
    draft_pool = eligible_players.copy()
    caps_pool = eligible_caps.copy()
    caps = random.sample(caps_pool, k=2)
    first_pick = False
    if random.randint(0, 1) < 0.5:
        first_pick = True
    picked_caps = True
    draft_pool.remove(caps[0])
    draft_pool.remove(caps[1])
    caps_pool.remove(caps[0])
    caps_pool.remove(caps[1])
    draft_teams[0].append(caps[0] if first_pick else caps[1])
    draft_teams[1].append(caps[1] if first_pick else caps[0])
    await ctx.send('{}, {}'.format(caps[0], caps[1]))
    await ctx.send('First pick: {}'.format(caps[0] if first_pick else caps[1]))


@client.command()
async def pick(ctx, *args):
    global draft_pool
    global draft_teams
    global current_team
    if not started_draft and not picked_caps:
        await ctx.send('Need to do !start_draft first')
        return
    if not picked_caps:
        await ctx.send('Need to do !random_caps first')
        return
    args = [word.lower().capitalize() for word in args]
    pick = ' '.join(args)
    if pick.lower() == 'random':
        pick = random.choice(draft_pool)
    if pick not in draft_pool:
        await ctx.send('Not a valid player, here is a list of the pool')
        await ctx.send(', '.join(draft_pool))
        return
    draft_teams[current_team].append(pick)
    draft_pool.remove(pick)
    current_team = 1 - current_team
    await ctx.send('{} was picked'.format(pick))
    if not draft_pool or (len(draft_teams[0]) == 4 and len(draft_teams[1]) == 4):
        await ctx.send('Draft finished, do !get_teams to see new teams')
        save_teams()
        reset()

def save_teams():
    players = players_sheet.get_all_values()[1:]
    names = [player[0] for player in players]
    for i in range(len(draft_teams)):
        for j in range(len(draft_teams[0])):
            teams_sheet.update_cell(i + 1, j + 1, draft_teams[i][j])
    row = 2
    for name in names:
        if name == draft_teams[0][0] or name == draft_teams[1][0]:
            players_sheet.update_cell(row, 5, 0)
        row += 1
     

def reset():
    global started_draft
    global picked_caps
    global eligible_players
    global eligible_caps
    global draft_pool
    global caps_pool
    global draft_teams
    global current_team
    started_draft = False
    picked_caps = False
    eligible_players = []
    eligible_caps = []
    draft_pool = []
    caps_pool = []
    draft_teams = [[], []]
    current_team = 0

@client.command()
async def reset_cap_rotation(ctx):
    num_players = len(players_sheet.col_values(1)) - 1
    for player in range(num_players):
        players_sheet.update_cell(player + 2, 5, 1)
    await ctx.send('Captain rotation reset. Everyone is now eligible')

@client.command()
async def add_player(ctx, *args):
    args = [word.lower().capitalize() for word in args]
    player_name = ' '.join(args)
    players = players_sheet.get_all_values()[1:]
    names = [player[0] for player in players]
    if player_name not in names:
        players_sheet.append_row([player_name, 0, 0, 1, 1, 'N/A', 0, 0])
        await ctx.send('{} added to bedwars roster (new player)'.format(player_name))
        return
    row = 2
    for name in names:
        if name == player_name:
            players_sheet.update_cell(row, 4, 1)
            await ctx.send('{} added to draft pool'.format(name))
            return
        row += 1

@client.command()
async def remove_player(ctx, *args):
    args = [word.lower().capitalize() for word in args]
    player_name = ' '.join(args)
    players = players_sheet.get_all_values()[1:]
    names = [player[0] for player in players]
    if player_name not in names:
        await ctx.send('Not a valid player to remove from draft pool, here is a list')
        await ctx.send(', '.join(names))
        return
    row = 2
    for name in names:
        if name == player_name:
            players_sheet.update_cell(row, 4, 0)
            await ctx.send('{} removed from draft pool'.format(name))
            return
        row += 1


@client.command()
@commands.has_role('Oracle')
async def remove_record(ctx, *args):
    args = [word.lower().capitalize() for word in args]
    player_name = ' '.join(args)
    players = players_sheet.get_all_values()[1:]
    names = [player[0] for player in players]
    if player_name not in names:
        await ctx.send('Not a valid player to delete from bedwars roster, here is a list')
        await ctx.send(', '.join(names))
        return
    row = 2
    for name in names:
        if name == player_name:
            players_sheet.delete_row(row)
            await ctx.send('{} removed from bedwars roster'.format(name))
            return
        row += 1

@client.command()
@commands.has_role('Oracle')
async def win(ctx, *args):
    args = [word.lower().capitalize() for word in args]
    player_name = ' '.join(args)
    players = players_sheet.get_all_values()[1:]
    teams = teams_sheet.get_all_values()
    names = [player[0] for player in players]
    if player_name not in names:
        await ctx.send('Not a valid player, here is a list')
        await ctx.send(', '.join(names))
        return
    winner = 1
    for name in teams[0]:
        if name == player_name:
            winner = 0
            break
    row = 2
    for name in names:
        if name in teams[winner]:
            wins = int(players_sheet.cell(row, 2).value)
            losses = int(players_sheet.cell(row, 3).value)
            streak = int(players_sheet.cell(row, 7).value)
            longest = int(players_sheet.cell(row, 8).value)
            players_sheet.update_cell(row, 2, wins + 1)
            if losses == 0:
                players_sheet.update_cell(row, 6, 'Infinity')
            else:
                players_sheet.update_cell(row, 6, round((wins + 1) / losses, 2))
            players_sheet.update_cell(row, 7, streak + 1)
            if streak + 1 > longest:
                players_sheet.update_cell(row, 8, streak + 1)
        elif name in teams[1 - winner]:
            wins = int(players_sheet.cell(row, 2).value)
            losses = int(players_sheet.cell(row, 3).value)
            players_sheet.update_cell(row, 3, losses + 1)
            players_sheet.update_cell(row, 6, round(wins / (losses + 1), 2))
            players_sheet.update_cell(row, 7, 0)
        row += 1
    await ctx.send('{} have won'.format(', '.join(teams[winner])))
    await ctx.send('{} have lost'.format(', '.join(teams[1 - winner])))

def sort_func(player):
    win_loss = player[3]
    wins = int(player[1])
    if win_loss == 'N/A':
        return -1
    if win_loss == 'Infinity':
        return 10000000000 + wins
    return 100 * float(win_loss) + wins

@client.command()
async def stats(ctx, *args):
    args = [word.lower().capitalize() for word in args]
    player_name = ' '.join(args)
    players = players_sheet.get_all_values()
    header = players[0]
    players = players[1:]
    names = [player[0] for player in players]
    for row in players:
        del row[3]
        del row[3]
    del header[3]
    del header[3]
    if player_name == '':
        players.sort(reverse=True, key=sort_func)
        players.insert(0, header)
        await ctx.send('```{}```'.format(tabulate(players, headers='firstrow')))
    elif player_name in names:
        player_stats = [players[names.index(player_name)]]
        player_stats.insert(0, header)
        await ctx.send('```{}```'.format(tabulate(player_stats, headers='firstrow')))
    else: 
        await ctx.send('Use a valid name or just do !stats for the full list')

@client.event
async def on_message(message):
    ctx = await client.get_context(message)
    await client.invoke(ctx)
    if message.channel.id == 606322549139308544:
        emoji = '💪🏿'
        await message.add_reaction(emoji)
    # emoji_ids = re.findall(r'<:\w*:\d*>', message.content)
    # emoji_ids = [int(e.split(':')[1].replace('>', '')) for e in emoji_ids]
    

@client.command()
@commands.has_role('Oracle')
async def kill(ctx):
    await client.logout()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send('Only the oracle knows this prayer')
    else:
        print(error)

@client.event
async def on_member_join(member):
    print('{} has joined'.format(member))
    role = get(member.guild.roles, name='Herald')
    await member.add_roles(role)
    await member.send('Welcome! You are a herald, so you only have voice chat permissions. If you are not a stranger, PM someone to get more permissions.')

@client.event
async def on_member_remove(member):
    print('{} has left'.format(member))

with open('token.txt', 'r') as f:
    token = f.read()
client.run(token)
