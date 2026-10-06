"""Ánh xạ infobox → thuộc tính vio:, tương tự mappings.dbpedia.org nhưng khai báo bằng Python.

Mỗi họ template (family) gồm:
  templates: tên template chuẩn; alias (redirect của template) được bổ sung lúc chạy.
  fields:    khoá infobox → (thuộc tính vio:, parser). Nhiều khoá có thể cùng trỏ một thuộc tính
             (template tiếng Việt và tiếng Anh dùng khoá khác nhau); khoá đứng trước được ưu tiên.
  series:    nhóm khoá đánh số (years1/clubs1/caps1/goals1…) → các CareerStation.

Parser: text, langtext, int, float, date, year, height, links, link_or_text, url.
Mọi khoá (kể cả không có trong fields) vẫn được ghi thành thuộc tính thô vip:<khoá>.
"""

CLASS_FAMILY = {
    "FootballPlayer": "football_player",
    "FootballClub": "football_club",
    "NationalFootballTeam": "football_club",
    "Stadium": "stadium",
    "University": "university",
    "Province": "province",
    "Country": "province",
}

MAPPINGS = {
    "football_player": {
        "templates": ["Thông tin tiểu sử bóng đá", "Infobox football biography"],
        "fields": {
            "birth_date": ("birthDate", "date"),
            "ngày sinh": ("birthDate", "date"),
            "birth_place": ("birthPlace", "links"),
            "nơi sinh": ("birthPlace", "links"),
            "height": ("height", "height"),
            "chiều cao": ("height", "height"),
            "position": ("position", "links"),
            "vị trí": ("position", "links"),
            "currentclub": ("currentClub", "links"),
            "câu lạc bộ hiện tại": ("currentClub", "links"),
            "clubnumber": ("shirtNumber", "int"),
            "số áo": ("shirtNumber", "int"),
        },
        "series": {
            "YouthStation": {"years": "youthyears{n}", "team": "youthclubs{n}"},
            "ClubStation": {"years": "years{n}", "team": "clubs{n}", "apps": "caps{n}", "goals": "goals{n}"},
            "NationalTeamStation": {
                "years": "nationalyears{n}",
                "team": "nationalteam{n}",
                "apps": "nationalcaps{n}",
                "goals": "nationalgoals{n}",
            },
        },
    },
    "football_club": {
        "templates": [
            "Hộp thông tin câu lạc bộ bóng đá",
            "Infobox football club",
            "Thông tin câu lạc bộ bóng đá",
        ],
        "fields": {
            "nickname": ("nickname", "langtext"),
            "biệt danh": ("nickname", "langtext"),
            "founded": ("founding", "date"),
            "thành lập": ("founding", "date"),
            "ground": ("ground", "links"),
            "sân": ("ground", "links"),
            "sân vận động": ("ground", "links"),
            "chairman": ("chairman", "links"),
            "chủ tịch": ("chairman", "links"),
            "manager": ("manager", "link_or_text"),
            "head coach": ("manager", "link_or_text"),
            "huấn luyện viên": ("manager", "link_or_text"),
            "league": ("league", "links"),
            "giải đấu": ("league", "links"),
            "website": ("homepage", "url"),
            "trang web": ("homepage", "url"),
        },
    },
    "stadium": {
        "templates": [
            "Hộp thông tin sân vận động",
            "Thông tin về sân vận động",
            "Infobox stadium",
            "Hộp thông tin địa điểm",
            "Infobox venue",
        ],
        "fields": {
            "location": ("locatedIn", "links"),
            "vị trí": ("locatedIn", "links"),
            "địa điểm": ("locatedIn", "links"),
            "opened": ("openingYear", "year"),
            "khánh thành": ("openingYear", "year"),
            "capacity": ("capacity", "int"),
            "sức chứa": ("capacity", "int"),
            "owner": ("owner", "links"),
            "chủ sở hữu": ("owner", "links"),
            "operator": ("operator", "links"),
            "quản lý": ("operator", "links"),
            "tenants": ("tenant", "links"),
            "bên thuê": ("tenant", "links"),
            "website": ("homepage", "url"),
        },
    },
    "university": {
        "templates": ["Thông tin trường học", "Infobox university", "Thông tin đại học", "Infobox school"],
        "fields": {
            "tên tiếng Anh": ("englishName", "text"),
            "native_name": ("englishName", "text"),
            "viết tắt": ("abbreviation", "text"),
            "abbreviation": ("abbreviation", "text"),
            "khẩu hiệu": ("motto", "langtext"),
            "motto": ("motto", "langtext"),
            "ngày thành lập": ("founding", "date"),
            "thành lập": ("founding", "date"),
            "established": ("founding", "date"),
            "hiệu trưởng": ("rector", "link_or_text"),
            "giám đốc": ("rector", "link_or_text"),
            "rector": ("rector", "link_or_text"),
            "president": ("rector", "link_or_text"),
            "sinh viên": ("numberOfStudents", "int"),
            "students": ("numberOfStudents", "int"),
            "giảng viên": ("academicStaffSize", "int"),
            "academic_staff": ("academicStaffSize", "int"),
            "thành phố": ("locatedIn", "links"),
            "city": ("locatedIn", "links"),
            "web": ("homepage", "url"),
            "website": ("homepage", "url"),
            "thành viên của": ("affiliation", "links"),
            "affiliations": ("affiliation", "links"),
        },
        # khi không có "sinh viên", cộng các bậc đào tạo
        "sum": {
            "numberOfStudents": [
                "sinh viên đại học",
                "sinh viên sau đại học",
                "nghiên cứu sinh",
                "undergrad",
                "postgrad",
            ]
        },
    },
    "province": {
        "templates": ["Thông tin đơn vị hành chính Việt Nam", "Infobox settlement", "Thông tin quốc gia"],
        "fields": {
            "diện tích": ("area", "float"),
            "dân số": ("population", "int"),
            "thời điểm dân số": ("populationYear", "year"),
            "vùng": ("region", "links"),
            "tỉnh lỵ": ("capital", "links"),
            "thủ phủ": ("capital", "links"),
            "mã hành chính": ("administrativeCode", "text"),
        },
    },
}

# Thuộc tính lấy từ nguồn nào trước (datatype/functional). Thuộc tính đối tượng thì gộp cả hai nguồn.
PRECEDENCE = {
    "birthDate": "wikidata",
    "height": "wikidata",
    "founding": "wikidata",
    "population": "wikidata",
    "area": "wikidata",
    "capacity": "wikidata",
    "openingYear": "wikidata",
    "homepage": "wikidata",
    "abbreviation": "wikidata",
    "shirtNumber": "infobox",
    "numberOfStudents": "infobox",
    "academicStaffSize": "infobox",
    "motto": "infobox",
    "administrativeCode": "infobox",
}
