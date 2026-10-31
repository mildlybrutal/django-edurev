"""Starter taxonomy for the three target roles P06 §13 requires: software development, data, testing.

This is institutional configuration, not student data. It is a starting point the
administrator is expected to edit. Required levels and weights below are illustrative
defaults chosen for this implementation, not values from the project specification.
"""

from .models import Level

CLUSTERS = {
    "programming": "Programming Languages",
    "backend": "Backend Development",
    "frontend": "Frontend Development",
    "data": "Data & Analytics",
    "databases": "Databases",
    "devops": "DevOps & Cloud",
    "testing": "Testing & Quality",
    "cs-fundamentals": "CS Fundamentals",
}

# name: (cluster, is_abstract, [synonyms], [parents])
SKILLS = {
    # Abstract categories that requirements can name.
    "Programming Language": ("programming", True, [], []),
    "Backend Framework": ("backend", True, [], []),
    "Frontend Framework": ("frontend", True, [], []),
    "SQL Database": ("databases", True, ["Relational Database", "RDBMS"], []),
    "NoSQL Database": ("databases", True, [], []),
    "Test Automation Framework": ("testing", True, [], []),
    "Data Visualisation Tool": ("data", True, ["Data Visualization Tool", "BI Tool"], []),
    # Languages
    "Python": ("programming", False, ["Python3", "Python 3"], ["Programming Language"]),
    "Java": ("programming", False, ["Core Java"], ["Programming Language"]),
    "JavaScript": ("programming", False, ["JS", "ECMAScript"], ["Programming Language"]),
    "TypeScript": ("programming", False, ["TS"], ["Programming Language"]),
    "C++": ("programming", False, ["CPP"], ["Programming Language"]),
    "SQL": ("databases", False, ["Structured Query Language"], []),
    # Backend
    "Django": ("backend", False, [], ["Backend Framework"]),
    "Flask": ("backend", False, [], ["Backend Framework"]),
    "Spring Boot": ("backend", False, ["Spring"], ["Backend Framework"]),
    "Node.js": ("backend", False, ["NodeJS", "Node"], ["Backend Framework"]),
    "Express": ("backend", False, ["Express.js", "ExpressJS"], ["Backend Framework"]),
    "REST APIs": ("backend", False, ["REST", "RESTful APIs", "REST API Design"], []),
    "Django REST Framework": ("backend", False, ["DRF"], ["REST APIs"]),
    "Authentication & Authorization": ("backend", False, ["Auth", "AuthN/AuthZ"], []),
    "Redis": ("databases", False, [], ["NoSQL Database"]),
    "Celery": ("backend", False, [], []),
    # Frontend
    "HTML & CSS": ("frontend", False, ["HTML", "CSS", "HTML5", "CSS3"], []),
    "React": ("frontend", False, ["ReactJS", "React.js"], ["Frontend Framework"]),
    "Next.js": ("frontend", False, ["NextJS"], ["React", "Frontend Framework"]),
    "Vue": ("frontend", False, ["Vue.js", "VueJS"], ["Frontend Framework"]),
    "Angular": ("frontend", False, ["AngularJS"], ["Frontend Framework"]),
    "Tailwind CSS": ("frontend", False, ["Tailwind"], ["HTML & CSS"]),
    # Databases
    "PostgreSQL": ("databases", False, ["Postgres", "PSQL"], ["SQL Database"]),
    "MySQL": ("databases", False, [], ["SQL Database"]),
    "MongoDB": ("databases", False, ["Mongo"], ["NoSQL Database"]),
    # DevOps
    "Git": ("devops", False, ["Version Control"], []),
    "Docker": ("devops", False, ["Containers", "Containerisation"], []),
    "Linux": ("devops", False, ["Unix", "Shell"], []),
    "CI/CD": ("devops", False, ["Continuous Integration", "GitHub Actions"], []),
    "AWS": ("devops", False, ["Amazon Web Services"], []),
    # CS fundamentals
    "Data Structures & Algorithms": ("cs-fundamentals", False, ["DSA", "Data Structures", "Algorithms"], []),
    "Object-Oriented Programming": ("cs-fundamentals", False, ["OOP", "OOPS"], []),
    "System Design": ("cs-fundamentals", False, ["Low Level Design", "High Level Design"], []),
    "Operating Systems": ("cs-fundamentals", False, ["OS"], []),
    "Computer Networks": ("cs-fundamentals", False, ["Networking"], []),
    "DBMS Concepts": ("cs-fundamentals", False, ["DBMS", "Database Management Systems"], []),
    # Data
    "Pandas": ("data", False, [], []),
    "NumPy": ("data", False, [], []),
    "Statistics": ("data", False, ["Probability & Statistics"], []),
    "Data Cleaning": ("data", False, ["Data Wrangling", "Data Preprocessing"], []),
    "Exploratory Data Analysis": ("data", False, ["EDA"], []),
    "Machine Learning": ("data", False, ["ML"], []),
    "scikit-learn": ("data", False, ["sklearn"], ["Machine Learning"]),
    "Excel": ("data", False, ["MS Excel", "Spreadsheets"], ["Data Visualisation Tool"]),
    "Power BI": ("data", False, ["PowerBI"], ["Data Visualisation Tool"]),
    "Tableau": ("data", False, [], ["Data Visualisation Tool"]),
    "ETL": ("data", False, ["Data Pipelines"], []),
    # Testing
    "Manual Testing": ("testing", False, ["Functional Testing"], []),
    "Test Case Design": ("testing", False, ["Test Cases", "Test Planning"], []),
    "Selenium": ("testing", False, ["Selenium WebDriver"], ["Test Automation Framework"]),
    "Playwright": ("testing", False, [], ["Test Automation Framework"]),
    "Cypress": ("testing", False, [], ["Test Automation Framework"]),
    "pytest": ("testing", False, ["PyTest"], ["Test Automation Framework"]),
    "JUnit": ("testing", False, [], ["Test Automation Framework"]),
    "API Testing": ("testing", False, ["Postman"], []),
    "Performance Testing": ("testing", False, ["Load Testing", "JMeter"], []),
    "Bug Tracking": ("testing", False, ["Defect Tracking", "JIRA"], []),
    "SDLC & STLC": ("testing", False, ["SDLC", "STLC"], []),
}

BEG, INT, ADV = Level.BEGINNER, Level.INTERMEDIATE, Level.ADVANCED

# role name: (description, [(skill, required level, weight, is_core)])
ROLES = {
    "Software Development Engineer": (
        "Builds and maintains application software across the backend and frontend.",
        [
            ("Programming Language", INT, 5, True),
            ("Data Structures & Algorithms", INT, 5, True),
            ("Object-Oriented Programming", INT, 3, True),
            ("Backend Framework", INT, 4, False),
            ("REST APIs", INT, 4, False),
            ("SQL Database", INT, 3, False),
            ("Git", INT, 2, False),
            ("Frontend Framework", BEG, 2, False),
            ("Docker", BEG, 2, False),
            ("System Design", BEG, 2, False),
            ("Operating Systems", BEG, 1, False),
            ("Computer Networks", BEG, 1, False),
        ],
    ),
    "Data Analyst": (
        "Prepares, analyses and visualises data to support decisions.",
        [
            ("SQL", INT, 5, True),
            ("Python", INT, 4, True),
            ("Statistics", INT, 4, True),
            ("Pandas", INT, 4, False),
            ("Data Cleaning", INT, 3, False),
            ("Exploratory Data Analysis", INT, 3, False),
            ("Data Visualisation Tool", INT, 3, False),
            ("Excel", INT, 2, False),
            ("NumPy", BEG, 2, False),
            ("Machine Learning", BEG, 1, False),
        ],
    ),
    "QA / Test Engineer": (
        "Designs and runs manual and automated tests to assure software quality.",
        [
            ("Manual Testing", INT, 4, True),
            ("Test Case Design", INT, 4, True),
            ("Test Automation Framework", INT, 4, True),
            ("Programming Language", BEG, 3, False),
            ("API Testing", INT, 3, False),
            ("SQL", BEG, 2, False),
            ("Bug Tracking", INT, 2, False),
            ("SDLC & STLC", INT, 2, False),
            ("Git", BEG, 1, False),
            ("Performance Testing", BEG, 1, False),
        ],
    ),
}
