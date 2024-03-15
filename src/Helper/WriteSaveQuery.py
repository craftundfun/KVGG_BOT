import string
from datetime import datetime


@DeprecationWarning
# writes the update SQL statement for the given data
def writeSaveQuery(table_name: string, primary_key: string, data: dict) -> (str, None):
    set_clauses = []
    how_many_None = 0

    # for every column
    for column, value in data.items():
        # don't touch the primary key
        if column == 'id':
            continue

        if value is None:
            set_clauses.append(f"{column} = %s")
            how_many_None += 1
        elif isinstance(value, datetime):
            value = value.strftime('%Y-%m-%d %H:%M:%S')
            set_clauses.append(f"{column} = '{value}'")
        else:
            set_clauses.append(f"{column} = '{value}'")

    set_clause = ', '.join(set_clauses)
    update_query = f"UPDATE {table_name} SET {set_clause} WHERE id = {primary_key}"
    parameters = ()

    # create Tuple for None-parameter
    for _ in range(how_many_None):
        parameters = parameters + (None,)

    return update_query, parameters
