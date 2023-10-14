def splitStringAtMaxLength(input_string: str, max_length: int = 2000) -> list[str]:
    """
    Splits the string at the nearest newline at 2000 characters.

    :param max_length:
    :param input_string:
    :return:
    """
    # Initialisieren Sie eine leere Liste, um die Teilstrings zu speichern.
    result = []

    # Starten Sie den Index, um den langen String zu durchlaufen.
    start = 0

    while start < len(input_string):
        # Suchen Sie nach einem Newline-Zeichen innerhalb der nächsten max_length Zeichen.
        end = start + max_length
        if end >= len(input_string):
            end = len(input_string)
        else:
            # Suchen Sie rückwärts nach einem Newline-Zeichen.
            while end > start and input_string[end] != '\n':
                end -= 1

        # Fügen Sie den Teilstring zwischen start und end (einschließlich end) zur Ergebnisliste hinzu.
        result.append(input_string[start:end + 1])

        # Aktualisieren Sie den Startindex für die nächste Iteration.
        start = end + 1

    return result
