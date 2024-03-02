USE testproject;

START TRANSACTION;

INSERT INTO statistic_log (time_online, type, discord_user_id, created_at)
SELECT 0, 'WEEK', id, '2024-02-19 00:00:15'
FROM discord
WHERE id NOT IN (4, 5, 19, 11); # Alex, Bjarne, Marius, Rene

# Bjarne
INSERT INTO statistic_log (time_online, type, discord_user_id, created_at)
VALUES (2890, 'WEEK', 5, '2024-02-19 00:00:15'); # fertig

# Marius
INSERT INTO statistic_log (time_online, type, discord_user_id, created_at)
VALUES (2621, 'WEEK', 19, '2024-02-19 00:00:15'); # fertig

# Rene
INSERT INTO statistic_log (time_online, type, discord_user_id, created_at)
VALUES (1224, 'WEEK', 11, '2024-02-19 00:00:15'); # fertig

# Alex
INSERT INTO statistic_log (time_online, type, discord_user_id, created_at)
VALUES (530, 'WEEK', 4, '2024-02-19 00:00:15'); # fertig

SELECT *
FROM statistic_log;

COMMIT;
