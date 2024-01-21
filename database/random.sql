USE beta;

SELECT id FROM quest WHERE time_type = 'daily';

DELETE FROM quest_discord_mapping WHERE id IN (SELECT id FROM quest WHERE time_type = 'daily');

USE testproject;

SELECT q.*, qdm.* FROM quest q INNER JOIN quest_discord_mapping qdm ON q.id = qdm.quest_id ORDER BY qdm.time_created DESC;

DROP TABLE counter;

SELECT rene_counter FROM discord WHERE username = "Bjarne";

SELECT * FROM counter_discord_mapping cdm INNER JOIN discord d ON cdm.discord_id = d.id INNER JOIN counter c ON cdm.counter_id = c.id;

WITH RankedCounters AS (
    SELECT
        cdm.counter_id,
        cdm.value,
        c.name,
        ROW_NUMBER() OVER (PARTITION BY cdm.counter_id ORDER BY cdm.value DESC) AS rn
    FROM
        counter_discord_mapping cdm
    INNER JOIN
        counter c ON cdm.counter_id = c.id
)
SELECT
    counter_id,
    value,
    name
FROM
    RankedCounters
WHERE
    rn <= 3;

SELECT d.username, cdm.value FROM counter_discord_mapping cdm INNER JOIN discord d ON cdm.discord_id = d.id WHERE cdm.value > 0 ORDER BY value DESC LIMIT 3;

SELECT qdm.current_value, q.value_to_reach, q.description, q.unit
                         FROM quest_discord_mapping AS qdm INNER JOIN quest AS q ON q.id = qdm.quest_id
                         WHERE q.time_type = 'daily' AND qdm.current_value < q.value_to_reach
                         AND qdm.discord_id = (
                         SELECT id
                         FROM discord AS d
                         WHERE d.user_id = 416967436617777163
                         );

DELETE FROM statistic_log;