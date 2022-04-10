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
    """ """
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
        self.players_in_match = []
        self.our_goals = 0
        self.opponent_goals = 0
        self.our_goals_minute = []
        self.opponent_goals_minute = []
        self.line_up = []
        self.our_team_is_home = True

    def run(self):
        self._set_match_soup()
        self._set_match_date()
        if self.match_date >= datetime.today():
            return
        self._set_our_team_is_home()
        self._set_players_in_match()
        self._set_home_away_goals_minute()

    def _set_match_soup(self):
        self.match_soup = BeautifulSoup(requests.get(domain + self.match_id).text, 'html5lib')

    def _set_match_date(self):
        self.match_date = dateparser.parse(
            self.match_soup.find("div", attrs={'class': 'text-center zapas-info'}).find("h2", recursive=False).text,
            settings={'DATE_ORDER': 'DMY'})

    def get_line_up(self):
        self.line_up = [player.text.replace(u'\xa0', u' ').strip() for player in
                        self.match_soup.find("h4", attrs={'class': 'text-center'}, text="Sestavy").parent
                            .find("strong", text=self.team_name).parent.findAll("a")]
        return self.line_up

    def _set_our_team_is_home(self):
        self.our_team_is_home = self.team_name == self.match_soup.find("div", attrs={'class': 'col-xs-6',
                                                                                     'style': 'text-align: center;'}).h2.a.text

    def _set_players_in_match(self):
        raw_text_line_up = self.match_soup.find("h4", attrs={'class': 'text-center'}, text="Sestavy").parent.find(
            "strong",
            text=self.team_name).parent.text
        raw_text_line_up = re.sub("\s+", " ", raw_text_line_up).replace(' - ', ' , ').replace(self.team_name,
                                                                                              '').replace('[-]', '')
        split_line_up = list(map(lambda x: x.strip(), raw_text_line_up.split(',')))
        for position in split_line_up:
            contents = [part.strip() for part in re.split('[\(\)]', position) if part.strip()]
            if len(contents) > 1:
                sub_time = int(contents[1].split(". ", 1)[0])
                self.players_in_match.append(PlayerInMatch(player=contents[0], in_minute=0, out_minute=sub_time))
                self.players_in_match.append(
                    PlayerInMatch(player=contents[1].split(". ", 1)[1], in_minute=sub_time, out_minute=MAX_MINUTE))
            else:
                self.players_in_match.append(PlayerInMatch(player=contents[0], in_minute=0, out_minute=MAX_MINUTE))

    def _set_home_away_goals_minute(self):
        [home_goals_div, away_goals_div] = self.match_soup.findAll("div", attrs={'class': 'col-xs-3'})
        if home_goals_div.div:
            home_goals_minute = re.findall(r'\d+', home_goals_div.div.text)
        else:
            home_goals_minute = []

        if away_goals_div.div:
            away_goals_minute = re.findall(r'\d+', away_goals_div.div.text)
        else:
            away_goals_minute = []

        if self.our_team_is_home:
            self.our_goals_minute = home_goals_minute
            self.opponent_goals_minute = away_goals_minute
        else:
            self.our_goals_minute = away_goals_minute
            self.opponent_goals_minute = home_goals_minute

    def update_plus_minus_statistics(self, plus_minus_statistics):
        for player in self.players_in_match:
            for our_goal in self.our_goals_minute:
                if player.in_minute < int(our_goal) < player.out_minute:
                    plus_minus_statistics[player.player] += 1
            for opponent_goal in self.opponent_goals_minute:
                if player.in_minute < int(opponent_goal) < player.out_minute:
                    plus_minus_statistics[player.player] -= 1
        return plus_minus_statistics


class CompetitionTeam:
    """
    Class representing chosen competition and chosen team within: default Okresní přebor Zlín - FC Slušovice B
    """
    common_url = "https://fotbalunas.cz/rozlosovani/soutez/"

    def __init__(self, competition_id: str, team_id: str, team_name: str, team_name_short: str):
        self.competition_id = competition_id
        self.team_id = team_id
        self.team_name = team_name
        self.team_name_short = team_name_short
        self.competition_team_soup = None
        self.all_season_matches = []
        self.all_players = []
        self.plus_minus_statistics = None

    def run(self):
        self._set_competition_team_soup()
        self._set_team_season_matches()
        self._set_team_players()
        self._initialize_plus_minus_statistics()
        self._set_plus_minus_statistics()
        self.get_plus_minus_statistics()

    def _set_competition_team_soup(self):
        self.competition_team_soup = BeautifulSoup(requests.get(CompetitionTeam.common_url + self.competition_id).text,
                                                   'html5lib')

    def _set_team_season_matches(self):
        all_matches = self.competition_team_soup.findAll('td', attrs={'class': 'zapas-item-utkani text-left'})
        self.all_season_matches = []
        for elem in all_matches:
            if self.team_name_short in elem.text:
                new_match = Match(match_id=elem.a['href'], team_name=self.team_name)
                new_match.run()
                if new_match.match_date < datetime.today():
                    self.all_season_matches.append(new_match)

    def _set_team_players(self):
        all_players_set = set()
        for match in self.all_season_matches:
            line_up = match.get_line_up()
            all_players_set.update(line_up)
        self.all_players = list(all_players_set)

    def _initialize_plus_minus_statistics(self):
        self.plus_minus_statistics = dict.fromkeys(self.all_players, 0)

    def _set_plus_minus_statistics(self):
        id = 0
        for match in self.all_season_matches:
            if id != 0:
                self.plus_minus_statistics = match.update_plus_minus_statistics(self.plus_minus_statistics)
            id += 1

    def get_plus_minus_statistics(self):
        return dict(sorted(self.plus_minus_statistics.items(), key=lambda item: item[1], reverse=True))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    competition_id = "311"  # OFS Zlín
    team_id = "4506"  # FC Slušovice B
    team_name = "FC Slušovice"
    team_name_short = "Slušovice"  # should be team_name, but trimmed from stop words (FC, FK, SK, ...) and ideally only one word: Valašské Klobouky -> Klobouky
    my_competition_team = CompetitionTeam(competition_id=competition_id, team_id=team_id,
                                          team_name=team_name, team_name_short=team_name_short)
    my_competition_team.run()
    print(my_competition_team.get_plus_minus_statistics())
