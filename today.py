import datetime
import os
import requests
from dateutil import relativedelta
from lxml import etree

# ── Configuration ─────────────────────────────────────────────────────────────
BIRTHDAY = datetime.datetime(2000, 10, 27, 0, 0)
USER_NAME = os.environ['USER_NAME']
HEADERS = {'authorization': 'token ' + os.environ['STATS_TOKEN']}
GRAPHQL_URL = 'https://api.github.com/graphql'
ACCOUNT_START_YEAR = 2021  # mdfojas joined GitHub March 2021


# ── Helpers ───────────────────────────────────────────────────────────────────
def graphql(query, variables):
    r = requests.post(GRAPHQL_URL, json={'query': query, 'variables': variables}, headers=HEADERS)
    if r.status_code != 200:
        raise Exception(f'GraphQL error {r.status_code}: {r.text}')
    return r.json()


# ── Age ───────────────────────────────────────────────────────────────────────
def compute_age():
    diff = relativedelta.relativedelta(datetime.datetime.today(), BIRTHDAY)
    def plural(n, word):
        return f'{n} {word}{"s" if n != 1 else ""}'
    return f'{plural(diff.years, "year")}, {plural(diff.months, "month")}, {plural(diff.days, "day")}'


# ── GitHub stats ──────────────────────────────────────────────────────────────
def get_repos_and_stars():
    query = '''
    query($login: String!) {
        user(login: $login) {
            repositories(first: 100, ownerAffiliations: [OWNER]) {
                totalCount
                edges { node { stargazers { totalCount } } }
            }
        }
    }'''
    data = graphql(query, {'login': USER_NAME})['data']['user']
    repos = data['repositories']['totalCount']
    stars = sum(e['node']['stargazers']['totalCount'] for e in data['repositories']['edges'])
    return repos, stars


def get_followers():
    query = 'query($login: String!) { user(login: $login) { followers { totalCount } } }'
    return graphql(query, {'login': USER_NAME})['data']['user']['followers']['totalCount']


def get_commits():
    # GitHub caps contributionsCollection to a 1-year window — sum year by year
    query = '''
    query($login: String!, $start: DateTime!, $end: DateTime!) {
        user(login: $login) {
            contributionsCollection(from: $start, to: $end) {
                contributionCalendar { totalContributions }
            }
        }
    }'''
    total = 0
    current_year = datetime.datetime.utcnow().year
    for year in range(ACCOUNT_START_YEAR, current_year + 1):
        result = graphql(query, {
            'login': USER_NAME,
            'start': f'{year}-01-01T00:00:00Z',
            'end': f'{year}-12-31T23:59:59Z',
        })
        total += result['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions']
    return total


# ── SVG mutation ──────────────────────────────────────────────────────────────
def update_svg(path, age, repos, stars, commits, followers):
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(path, parser)
    root = tree.getroot()

    def set_text(elem_id, text):
        matches = root.xpath(f'//*[@id="{elem_id}"]')
        if matches:
            matches[0].text = text

    # Adjust dot padding so the value column stays roughly aligned
    # TARGET=55: ". Uptime: " + dots + " " + age = 55 => dots = 44 - len(age)
    n_dots = max(3, 44 - len(age))
    set_text('uptime_dots', ': ' + '.' * n_dots + ' ')
    set_text('uptime_data', age)

    set_text('repos_data', str(repos))
    set_text('stars_data', str(stars))
    set_text('commits_data', str(commits))
    set_text('followers_data', str(followers))

    tree.write(path, xml_declaration=True, encoding='UTF-8', pretty_print=False)
    print(f'  Updated {path}')


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Fetching GitHub stats...')
    age = compute_age()
    repos, stars = get_repos_and_stars()
    followers = get_followers()
    commits = get_commits()

    print(f'  Age:       {age}')
    print(f'  Repos:     {repos}')
    print(f'  Stars:     {stars}')
    print(f'  Commits:   {commits}')
    print(f'  Followers: {followers}')

    print('Writing SVGs...')
    update_svg('dark_mode.svg', age, repos, stars, commits, followers)
    update_svg('light_mode.svg', age, repos, stars, commits, followers)
    print('Done.')
