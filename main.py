from dataclasses import dataclass, field
from datetime import datetime
import dateparser
import regex as re

from bs4 import BeautifulSoup
import requests

domain = "https://fotbalunas.cz"
MAX_MINUTE = 500


@dataclass
class PlayerInMatch:
    player: str
    in_minute: int = field(default=0)
    out_minute: int = field(default=MAX_MINUTE)


class Match:
    """
    Class representing a match of the chosen team
    """

    def __init__(self, match_id: str, team_name: str):
        self.match_id = match_id
        self.team_name = team_name
        self.match_soup = None
        self.match_date = None
        self.our_goals = 0
        self.opponent_goals = 0
        self.our_goals_minute = []
        self.opponent_goals_minute = []
        self.line_up = []
        self.our_team_is_home = True

    def run(self):
        self._set_match_soup()

    def _set_match_soup(self):
        self.match_soup = BeautifulSoup(requests.get(domain + self.match_id).text, 'html5lib')

    def _set_match_date(self):
        self.match_date = dateparser.parse(
            self.match_soup.find("div", attrs={'class': 'text-center zapas-info'}).find("h2", recursive=False).text,
            settings={'DATE_ORDER': 'DMY'})

    def get_line_up(self):
        self.line_up = [player.text.replace(u'\xa0', u' ') for player in
                        self.soup_match.find("h4", attrs={'class': 'text-center'}, text="Sestavy").parent
                            .find("strong", text=team_name).parent.findAll("a")]
        return self.line_up


class Team:
    """
    Class representing chosen team - default FC Slušovice
    """
    common_url = "https://fotbalunas.cz/tym/"

    def __init__(self, team_id: str):
        self.team_id = team_id
        self.team_soup = None
        self.team_name = None
        self.all_available_matches = []
        self.all_season_matches = []
        self.all_season_players = []
        self.plus_minus_statistics = None
        self.all_players = []

    def run(self):
        self._set_team_soup()
        self._set_team_name()
        self._set_all_available_matches()
        self._set_all_season_matches()
        self._set_all_season_players()

    def _set_team_soup(self):
        self.team_soup = BeautifulSoup(requests.get(Team.common_url + self.team_id).text, 'html5lib')

    def _set_team_name(self):
        self.team_name = self.team_soup.find('h1').text

    def _set_all_available_matches(self):
        self.all_available_matches = [elem.a['href'] for elem in
                                      soup_team.findAll('td', attrs={'class': 'zapas-item-utkani text-left'})]

    def _set_all_season_matches(self):
        for match_id in self.all_available_matches:
            new_match = Match(match_id, self.team_name)
            current_date = datetime.now()
            if bool(current_date.month >= 7) + current_date.year == bool(
                    new_match.match_date.month >= 7) + new_match.match_date.year:
                self.all_season_matches.append(match_id)

    def _set_all_season_players(self):
        all_players_set = set()
        for match_id in self.all_season_matches:
            new_match = Match(match_id, self.team_name)
            line_up = new_match.get_line_up()
            all_players_set.update(line_up)
        self.all_players = list(all_players_set)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    URL = "https://fotbalunas.cz/tym/4596/"
    r = requests.get(URL)
    soup_team = BeautifulSoup(r.text, 'html5lib')
    team_name = soup_team.find('h1').text
    team_last_matches = [elem.a['href'] for elem in
                         soup_team.findAll('td', attrs={'class': 'zapas-item-utkani text-left'})]
    team_season_matches = []
    for match in team_last_matches:
        r = requests.get(domain + match)
        soup_match = BeautifulSoup(r.text, 'html5lib')
        match_date = dateparser.parse(
            soup_match.find("div", attrs={'class': 'text-center zapas-info'}).find("h2", recursive=False).text,
            settings={'DATE_ORDER': 'DMY'})
        current_date = datetime.now()
        if bool(current_date.month >= 7) + current_date.year == bool(match_date.month >= 7) + match_date.year:
            team_season_matches.append(match)

    all_players_set = set()
    for match in team_season_matches:
        r = requests.get(domain + match)
        soup_match = BeautifulSoup(r.text, 'html5lib')
        line_up = [player.text.replace(u'\xa0', u' ') for player in
                   soup_match.find("h4", attrs={'class': 'text-center'}, text="Sestavy").parent
                       .find("strong", text=team_name).parent.findAll("a")]
        all_players_set.update(line_up)
    all_players = list(all_players_set)
    plus_minus_statistics = dict.fromkeys(all_players, 0)
    for match in team_season_matches:
        r = requests.get(domain + match)
        soup_match = BeautifulSoup(r.text, 'html5lib')
        our_team_is_home = bool(
            team_name == soup_match.find("div", attrs={'class': 'col-xs-6', 'style': 'text-align: center;'}).h2.a.text)
        raw_text_line_up = soup_match.find("h4", attrs={'class': 'text-center'}, text="Sestavy").parent.find("strong",
                                                                                                             text=team_name).parent.text
        raw_text_line_up = re.sub("\s+", " ", raw_text_line_up).replace(' - ', ' , ').replace(team_name, '').replace(
            '[-]', '')
        split_line_up = list(map(lambda x: x.strip(), raw_text_line_up.split(',')))
        players_in_match = []
        for position in split_line_up:
            contents = [part.strip() for part in re.split('[\(\)]', position) if part.strip()]
            if len(contents) > 1:
                sub_time = int(contents[1].split(". ", 1)[0])
                players_in_match.append(PlayerInMatch(player=contents[0], in_minute=0, out_minute=sub_time))
                players_in_match.append(
                    PlayerInMatch(player=contents[1].split(". ", 1)[1], in_minute=sub_time, out_minute=MAX_MINUTE))
            else:
                players_in_match.append(PlayerInMatch(player=contents[0], in_minute=0, out_minute=MAX_MINUTE))

        [home_goals_div, away_goals_div] = soup_match.findAll("div", attrs={'class': 'col-xs-3'})
        if home_goals_div.div:
            home_goals_minute = re.findall(r'\d+', home_goals_div.div.text)
        else:
            home_goals_minute = []

        if away_goals_div.div:
            away_goals_minute = re.findall(r'\d+', away_goals_div.div.text)
        else:
            away_goals_minute = []
        if our_team_is_home:
            our_goals_minute = home_goals_minute
            opponent_goals_minute = away_goals_minute
        else:
            our_goals_minute = away_goals_minute
            opponent_goals_minute = home_goals_minute

        for player in players_in_match:
            for our_goal in our_goals_minute:
                if player.in_minute <= int(our_goal) <= player.out_minute:
                    plus_minus_statistics[player.player] += 1
            for opponent_goal in opponent_goals_minute:
                if player.in_minute <= int(opponent_goal) <= player.out_minute:
                    plus_minus_statistics[player.player] -= 1

    print(plus_minus_statistics)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
