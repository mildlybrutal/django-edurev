"""Fictional reference data for the demo. Company names, people and numbers are invented."""

FIRST_NAMES = [
    "Aarav",
    "Diya",
    "Ishaan",
    "Ananya",
    "Kabir",
    "Meera",
    "Rohan",
    "Saanvi",
    "Vihaan",
    "Aditi",
    "Arjun",
    "Kavya",
    "Reyansh",
    "Myra",
    "Dev",
    "Tara",
    "Nikhil",
    "Zara",
    "Aryan",
    "Riya",
    "Kunal",
    "Isha",
    "Yash",
    "Nisha",
    "Harsh",
    "Pooja",
    "Siddharth",
    "Simran",
    "Varun",
    "Anika",
]
LAST_NAMES = ["Sharma", "Verma", "Gill", "Kaur", "Singh", "Mehta", "Iyer", "Nair", "Rao", "Bose", "Das", "Khan"]

DEPARTMENTS = [
    ("CSE", "Computer Science & Engineering"),
    ("IT", "Information Technology"),
    ("ECE", "Electronics & Communication"),
    ("ME", "Mechanical Engineering"),
]

# Skill bundles a synthetic student's projects draw from (skill name, claimed level 1-4).
PROFILES = {
    "backend": [
        ("Python", 3),
        ("Django", 3),
        ("REST APIs", 3),
        ("PostgreSQL", 2),
        ("Docker", 2),
        ("Git", 2),
        ("Redis", 1),
        ("Data Structures & Algorithms", 2),
    ],
    "java": [
        ("Java", 3),
        ("Spring Boot", 2),
        ("MySQL", 2),
        ("Object-Oriented Programming", 3),
        ("Git", 2),
        ("Data Structures & Algorithms", 3),
    ],
    "frontend": [("JavaScript", 3), ("React", 3), ("TypeScript", 2), ("HTML & CSS", 3), ("Next.js", 2), ("Git", 2)],
    "data": [
        ("Python", 3),
        ("Pandas", 3),
        ("SQL", 3),
        ("Statistics", 2),
        ("Exploratory Data Analysis", 2),
        ("Power BI", 2),
        ("Excel", 3),
        ("NumPy", 2),
    ],
    "testing": [
        ("Manual Testing", 3),
        ("Test Case Design", 3),
        ("Selenium", 2),
        ("API Testing", 2),
        ("SQL", 2),
        ("Bug Tracking", 2),
        ("Java", 1),
    ],
}

PROJECT_TITLES = {
    "backend": ["Library management REST API", "Expense tracker backend", "URL shortener service"],
    "java": ["Inventory system in Spring Boot", "Hostel booking portal"],
    "frontend": ["Portfolio site in Next.js", "Kanban board in React"],
    "data": ["Placement trends dashboard", "Retail sales EDA notebook"],
    "testing": ["Automated test suite for a demo shop", "API regression suite"],
}

RESOURCES = [
    (
        "Django",
        2,
        "Django tutorial (official)",
        "https://docs.djangoproject.com/en/5.2/intro/tutorial01/",
        "documentation",
    ),
    ("Django", 3, "Django documentation: topics", "https://docs.djangoproject.com/en/5.2/topics/", "documentation"),
    ("Docker", 2, "Docker: Get started", "https://docs.docker.com/get-started/", "documentation"),
    (
        "PostgreSQL",
        2,
        "PostgreSQL tutorial (official)",
        "https://www.postgresql.org/docs/current/tutorial.html",
        "documentation",
    ),
    (
        "REST APIs",
        2,
        "Django REST Framework tutorial",
        "https://www.django-rest-framework.org/tutorial/quickstart/",
        "documentation",
    ),
    ("React", 2, "React: Learn", "https://react.dev/learn", "documentation"),
    ("Redis", 1, "Redis: Get started", "https://redis.io/docs/latest/get-started/", "documentation"),
    ("Data Structures & Algorithms", 2, "Practice problem sets (institution DSA track)", "", "practice"),
    (
        "System Design",
        1,
        "System design primer",
        "https://github.com/donnemartin/system-design-primer",
        "documentation",
    ),
    (
        "SQL",
        2,
        "PostgreSQL SELECT tutorial",
        "https://www.postgresql.org/docs/current/tutorial-select.html",
        "documentation",
    ),
    (
        "Pandas",
        2,
        "pandas: 10 minutes to pandas",
        "https://pandas.pydata.org/docs/user_guide/10min.html",
        "documentation",
    ),
    (
        "Selenium",
        2,
        "Selenium: Getting started",
        "https://www.selenium.dev/documentation/webdriver/getting_started/",
        "documentation",
    ),
]

# Company names are real campus recruiters, used only as labels. This JD text is written for the
# demo; it is not an actual Capgemini posting.
BACKEND_JD = """Capgemini — Backend Engineer, 2027 batch (sample JD for the demo)

We are hiring backend engineers to build payment and ledger services for client projects.

Responsibilities
- Design and build REST APIs in Python and Django.
- Model data in PostgreSQL and optimise queries.
- Containerise services; familiarity with Docker is required.

Requirements
- Strong Python and Django skills are a must.
- Solid understanding of DSA is essential.
- Experience with Git.
- Good to have: exposure to Redis and basic System Design.

Eligibility: B.Tech CSE / IT, minimum 7.0 CGPA, no active backlogs.
"""
