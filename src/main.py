from collections import namedtuple
import psycopg2

Bonus = namedtuple('Bonus',
                   'id,number,round,category_id,subcategory_id,quinterest_id,tournament_id,leadin,created_at,updated_at,errors_count,formatted_leadin')
BonusPart = namedtuple('BonusPart',
                       'id,bonus_id,text,answer,formatted_text,formatted_answer,created_at,updated_at,number,wikipedia_url')
Tournament = namedtuple('Tournament', 'id,year,name,difficulty,quality,address,type,link,created_at,updated_at')
Tossup = namedtuple('Tossup', 'id,text,answer,number,tournament_id,category_id,subcategory_id,round,created_at,updated_at,'
                              'quinterest_id,formatted_text,errors_count,formatted_answer,wikipedia_url')
connection = None

category_id_to_alias_map = {
    'geo': 20,
    'geography': 20,
    'hist': 18,
    'history': 18,
    'lit': 15,
    'literature': 15,
    'm': 14,
    'myth': 14,
    'p': 25,
    'philo': 25,
    'r': 19,
    'religion': 19,
    'sci': 17,
    'science': 17,
    'ss': 22,
    'socialscience': 22,
    'trash': 16,
    'ce': 26,
    'currentevents': 26,
    'fa': 21,
    'finearts': 21
}

subcategory_id_to_alias_map = {
    # 40: ['cea', 'ceamerican'],
    # 42: ['ceo', 'ceother'],
    # 35: ['faam', 'fineartsamerican'],
    # 27: ['faav', 'fineartsaudiovisual'],
    # 8: ['faa', 'fineartsauditory'],
    # 45: ['fab', 'fineartsbritish'],
    # 50: ['fae', 'fineartseuropean'],
    # 77: ['fao', 'opera', 'fineartsopera'],
    # 25: ['faot', 'fineartsother'],
    # 2: ['fav', 'fineartsvisual'],
    # 43: ['faw', 'fineartsworld'],
    # 38: ['geoa', 'geoamerican'],
    'bio': 14,
    'biology': 14,
    'chem': 5,
    'chemistry': 5,
    'cs': 23,
    'math': 26,
    'physics': 18

    # 14: ['bio', 'biology'],
    # 5: ['chem', 'chemistry'],
    # 23: ['cs', 'compsci', 'computerscience'],
    # 26: ['math'],
    # 10: ['osci', 'otherscience'],
    # 18: ['physics']
    # TODO finish this later i'm lazy
}

class GlobalState:
    sessions = []
    skip_message = None

state = GlobalState()

def get_global_state():
    global state
    return state

def get_db_connection():
    global connection
    if connection is None:
        connection = psycopg2.connect('dbname=quizdb user=postgres')
    return connection


tournaments = []
def get_tournaments():
    global tournaments
    if len(tournaments) == 0:
        conn = get_db_connection()
        tournaments = read_tournaments(conn)
    return tournaments

def read_tournaments(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tournaments')
    return list(map(Tournament._make, cursor.fetchall()))


tournament_series = {'scop': 'scop', 'pace': 'pace', 'rmbat': 'rmbat', 'bhsat': 'bhsat', 'acf_regs': 'acf regionals', 'acf_fall': 'acf fall', 'co': 'chicago open'}


def get_bonus_batch(conn, arguments):
    # Who needs ORMs anyway amirite? This is literally the jankiest shit i've ever written but it works so...
    # TODO: use an ORM

    difficulties = []
    categories = []
    subcategories = []
    selected_tournaments = []
    for arg in arguments:
        if arg[0].isdigit():
            # Difficulty or year
            # Check if range
            if len(arg.split('-')) > 1:
                values = arg.split('-')
                difficulties = list(range(int(values[0]), int(values[1]) + 1))
            elif 0 < int(arg) < 10:
                difficulties = [int(arg)]
            else:
                # assume year
                if selected_tournaments[-1][1] == -1:
                    selected_tournaments[-1] = (selected_tournaments[-1][0], int(arg))
        else:
            # Category, subcategory, or tournament
            for k in subcategory_id_to_alias_map.keys():
                if arg == k:
                    subcategories.append(str(subcategory_id_to_alias_map[k]))
            for k in category_id_to_alias_map.keys():
                if arg == k:
                    categories.append(str(category_id_to_alias_map[k]))
            if arg in tournament_series:
                selected_tournaments.append((tournament_series[arg], -1))

    category_conditional = '('
    category_conditional += ' OR '.join([f'bonuses.category_id={category}' for category in categories])
    category_conditional += ')'

    difficulty_conditional = '('
    difficulty_conditional += ' OR '.join([f'tournaments.difficulty={difficulty}' for difficulty in difficulties])
    difficulty_conditional += ')'

    subcategory_conditional = '('
    subcategory_conditional += ' OR '.join([f'bonuses.subcategory_id={subcategory}' for subcategory in subcategories])
    subcategory_conditional += ')'

    matching_tournament_records = []

    for t in selected_tournaments:
        if t[1] == -1:
            matching_tournament_records.extend([i for i in get_tournaments() if t[0] in i.name.lower()])
        else:
            matching_tournament_records.extend([i for i in get_tournaments() if t[0] in i.name.lower() and str(t[1]) in i.name.lower()])

    if len(matching_tournament_records) == 0 and len(selected_tournaments) != 0:
        raise Exception('No tournament matches your query')

    tournament_conditional = '(' if len(matching_tournament_records) > 0 else ''
    tournament_conditional += ' OR '.join([f'tournaments.id={t.id}' for t in matching_tournament_records]) + ')'

    if len(difficulties) > 0:
        sql_command = 'SELECT bonuses.* FROM bonuses,tournaments WHERE bonuses.tournament_id=tournaments.id AND ' + difficulty_conditional
        if len(subcategories) > 0:
            sql_command += ' AND ' + subcategory_conditional
        if len(categories) > 0:
            sql_command += ' AND ' + category_conditional
        if len(selected_tournaments) > 0:
            sql_command += ' AND ' + tournament_conditional
    elif len(subcategories) > 0 or len(categories) > 0 or len(tournament_conditional) > 0:
        sql_command = 'SELECT bonuses.* FROM bonuses,tournaments WHERE bonuses.tournament_id=tournaments.id'
        if len(subcategories) > 0:
            sql_command += ' AND ' + subcategory_conditional
        if len(categories) > 0:
            sql_command += ' AND ' + category_conditional
        if len(selected_tournaments) > 0:
            sql_command += ' AND ' + tournament_conditional
    else:
        sql_command = 'SELECT * FROM bonuses'

    sql_command += " ORDER BY RANDOM() LIMIT 20;"
    print(f'Executing {sql_command}')
    return get_bonus_batch_raw(conn, sql_command)


def get_bonus_batch_raw(conn, sql_command):
    bonuses = []
    cursor = conn.cursor()
    cursor.execute(sql_command)
    for bonus in map(Bonus._make, cursor.fetchall()):
        cursor.execute(f"SELECT * FROM bonus_parts WHERE bonus_id={bonus.id} ORDER BY number")
        bonus_parts = list(map(BonusPart._make, cursor.fetchall()))
        if len(bonus_parts) == 0:
            # Unusable
            continue
        cursor.execute(f'SELECT * FROM tournaments WHERE id={bonus.tournament_id}')
        tournament = list(map(Tournament._make, cursor.fetchall()))
        assert len(tournament) == 1
        bonuses.append((bonus, bonus_parts, tournament[0]))

    return bonuses





