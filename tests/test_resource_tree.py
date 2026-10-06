"""Tab Cây tài nguyên (vidbpedia/web/resource_tree.py): cây lớp vio: → tên thực thể, không có thuộc tính.

pytest tests/test_resource_tree.py -v
"""

import pytest

from vidbpedia.common import DATASET
from vidbpedia.vocab import VIO, VRES
from vidbpedia.web.resource_page import ResourceView
from vidbpedia.web.resource_tree import ResourceTree

CP = VRES["Nguyễn_Công_Phượng"]


@pytest.fixture(scope="module")
def tree(graph):
    return ResourceTree(ResourceView.from_files(graph, DATASET + ".nt"))


def test_class_hierarchy(tree):
    assert tree.parent[VIO.FootballPlayer] == VIO.Athlete
    assert tree.parent[VIO.Person] is None
    assert VIO.University in tree.children[VIO.EducationalInstitution]


def test_direct_members_like_folders(tree):
    # Công Phượng từng khoác áo đội tuyển → nằm ở lớp con NationalTeamPlayer, không lặp lại ở FootballPlayer
    assert CP in tree.direct[VIO.NationalTeamPlayer]
    assert CP not in tree.direct[VIO.FootballPlayer]
    assert CP in tree.members[VIO.Person]
    players = tree.members[VIO.FootballPlayer]
    assert players == tree.direct[VIO.FootballPlayer] | tree.direct[VIO.NationalTeamPlayer]


def test_full_tree_has_names_but_no_data(tree):
    html = tree.full
    assert "vio:FootballPlayer" in html and "dbo:SoccerPlayer" in html
    assert "Nguyễn Công Phượng" in html and "/resource/" in html
    assert "Thể loại Wikipedia" in html and "Trang đổi hướng" in html
    assert "1995-01-21" not in html and "dbo:abstract" not in html  # chỉ tên, không có thuộc tính


def test_filter(tree):
    html = tree.render("cong phuong")
    assert "Nguyễn Công Phượng" in html and "Đặng Văn Lâm" not in html
    assert "Không có tài nguyên nào" in tree.render("zzzz không có")
