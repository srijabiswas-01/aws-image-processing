import os

import pymysql
from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    """
    Create a connection to the Amazon RDS MySQL database.
    """

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        port=int(
            os.environ.get(
                "DB_PORT",
                3306
            )
        ),

        cursorclass=pymysql.cursors.DictCursor,

        # Transaction control is handled explicitly
        # using connection.commit() and connection.rollback().
        autocommit=False,

        # Helps detect broken/stale connections.
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )