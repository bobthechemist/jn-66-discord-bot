import sqlite3
import logging
from datetime import datetime

log = logging.getLogger(__name__)

'''
A message is a dictionary containing the keys author, timestamp and message
message database contains the entire conversation between bot and human
musings contains specific thoughts of the user
tasks contains task items created by the user
'''

class DatabaseManager:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name) # User should add the .db extension
        log.info(f"Using {db_name} for the database.")
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            due_date TEXT NOT NULL,
            date_completed TEXT,
            creation_date TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            estimated_time INTEGER,
            actual_time INTEGER
        )
        ''')
        self.conn.commit()

        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY,
            message TEXT NOT NULL,
            author TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        ''')
        self.conn.commit()

        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS musings (
            musing_id INTEGER PRIMARY KEY,
            musing TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        ''')
        self.conn.commit()
    
    def store(self, table, record):
        placeholders = ', '.join(['?'] * len(record))
        columns = ', '.join(record.keys())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self.cursor.execute(sql, tuple(record.values()))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def store_message(self, message):
        return self.store("messages", message)

    def store_task(self, task):
        return self.store('tasks', task)

    def store_musing(self, message):
        log.debug(message)
        return self.store("musings", message)
        
    def fetch(self, table, criteria=None):
        """
        Fetches records from a table based on a flexible criteria dictionary.
        
        Criteria values can be a simple value for an exact match ('='),
        or a tuple containing an operator and a value, e.g., ('<=', '2025-08-04').
        """
        query = f"SELECT * FROM {table}"
        if criteria:
            where_clauses = []
            parameters = []
            for key, value in criteria.items():
                if isinstance(value, tuple) and len(value) == 2:
                    # Handle tuples like ('<=', 'some_value')
                    operator, param_value = value
                    # Basic validation to prevent SQL injection with operators
                    if operator in ['=', '<', '>', '<=', '>=', '!=', 'LIKE']:
                        where_clauses.append(f"{key} {operator} ?")
                        parameters.append(param_value)
                else:
                    # Handle simple values for an exact match
                    where_clauses.append(f"{key} = ?")
                    parameters.append(value)
            
            if where_clauses:
                where_clause_str = " AND ".join(where_clauses)
                query += f" WHERE {where_clause_str}"
                self.cursor.execute(query, parameters)
            else:
                self.cursor.execute(query) # Fallback if criteria was empty or invalid
        else:
            self.cursor.execute(query)
            
        rows = self.cursor.fetchall()
        field_names = [description[0] for description in self.cursor.description]
        results = [dict(zip(field_names, row)) for row in rows]
        return results

    def fetch_tasks(self, criteria = None):
        return self.fetch("tasks", criteria)
        
    
    def fetch_messages(self, criteria = None):
        return self.fetch("messages", criteria)
        
    
    def fetch_musings(self, criteria = None):
        return self.fetch("musings", criteria)
        
    
    def update_task(self, task_id, updates):
        set_clauses = []
        parameters = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = ?")
            parameters.append(value)
        set_clause = ", ".join(set_clauses)
        parameters.append(task_id)
        
        sql = f"UPDATE tasks SET {set_clause} WHERE task_id = ?"
        self.cursor.execute(sql, parameters)
        self.conn.commit()
    
    def delete_task(self, task_id):
        sql = "DELETE FROM tasks WHERE task_id = ?"
        self.cursor.execute(sql, (task_id,))
        self.conn.commit()    

    def count_tasks(self, criteria):
        """Counts tasks based on a given criteria dictionary"""
        query = "SELECT COUNT(*) FROM tasks"
        parameters = []
        if criteria:
            where_clauses = [f"{key} < ?" if 'date' in key else f"{key} = ?" for key in criteria.keys()]
            parameters = list(criteria.values())
            query += " WHERE " + " AND ".join(where_clauses)

        self.cursor.execute(query,parameters)
        count = self.cursor.fetchone()[0]
        return count
    
    def bulk_update_tasks(self, criteria, updates):
        """
        Updates multiple task entries matchint the provided criteria with the provided updates
        
        example:
        criteria = {'status': 'pending', 'due_date': '2025-07-01'}
        updates = {'status': 'expired', 'notes': 'Marked expired by admin tool'}
        """
        if not criteria or not updates:
            log.error("Bulk update called with empty criteria or updates")
            return 0
        
        # Build the SET part of the query
        set_clauses = [f"{key} = ?" for key in updates.keys()]
        set_clause = ", ".join(set_clauses)

        # Build the WHERE part of the query
 
        # Use '<' for date to find tasks before the provided date
        where_clauses = [f"{key} < ?" if 'date' in key else f"{key} = ?" for key in criteria.keys()]
        where_clause = " AND ".join(where_clauses)

        # Combine and execute
        parameters = list(updates.values()) + list(criteria.values())
        sql = f"UPDATE tasks SET {set_clause} WHERE {where_clause}"

        self.cursor.execute(sql, parameters)
        self.conn.commit()

        # Return the number of rows  changed
        return self.cursor.rowcount
