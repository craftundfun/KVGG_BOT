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

USE beta;

SELECT d.id AS discord_id, cds.value, cds.statistic_time, cds.statistic_type
FROM discord d LEFT JOIN current_discord_statistic cds ON d.id = cds.discord_id
WHERE cds.statistic_time = 'WEEK' OR cds.statistic_time IS NULL;

INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (88, 12, 'Alex WSL-Corruption zeigen', '2024-01-06 21:00:31', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (98, 12, 'Spino knuddeln', '2024-01-20 01:10:23', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (97, 12, 'Gacha Kind', '2024-01-20 01:00:23', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (96, 12, 'Spino Eier', '2024-01-20 00:10:22', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (95, 12, 'Spino knuddeln', '2024-01-19 22:50:23', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (93, 12, 'Spinos', '2024-01-19 22:05:22', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (92, 12, 'Spino-Eier', '2024-01-18 23:10:49', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (91, 12, 'Argentaven prägen', '2024-01-17 22:13:14', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (90, 12, 'Spino prägen', '2024-01-17 22:07:14', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (89, 12, 'BS-Klausurenanmeldung', '2024-01-12 21:00:08', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (99, 12, 'Gacha knuddeln', '2024-01-20 01:50:22', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (87, 12, 'Pokemon Go Daily Quest', '2024-02-02 21:00:36', 0, 1440, 1, '2024-02-03 21:00:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (86, 12, 'rBAR', '2024-01-04 17:00:27', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (84, 12, 'Bananenmilch von Felix trinken', null, 0, null, 1, '2025-02-23 20:00:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (83, 12, '10€ für Rene Blizzard Umbenennung', null, 0, null, 1, '2024-11-20 12:00:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (82, 12, 'Gratulation', '2023-12-21 23:55:43', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (81, 12, 'Death Stranding Film', null, 0, null, 1, '2025-01-01 00:00:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (1, 12, 'Test', '2023-08-09 21:07:43', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (107,12, 'Eule prägen', '2024-01-22 01:33:03', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (118,12, 'Tablet vom Strom nehmen', '2024-01-30 21:43:37', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (117,12, 'Project U', '2024-02-01 16:00:36', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (115,12, 'XP-Spin', null, 0, null, 0, '2024-02-03 20:22:34', 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (113,12, 'XP checken', '2024-01-26 01:36:00', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (111,12, 'Project U - Marius', '2024-01-25 22:22:23', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (110,12, 'Binary Millenium in 7 Sekunden', null, 0, null, 1, '2038-01-19 03:14:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (109,12, 'Eulen paaren', '2024-01-22 21:27:03', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (108,12, 'CEOofCEOs knuddeln', '2024-01-22 04:38:03', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (77, 12, 'GTA VI wurde veröffentlicht', null, 0, null, 1, '2025-12-31 23:59:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (106,12, 'Eulen fertig', '2024-01-22 00:36:55', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (105,12, 'Spino knuddeln', '2024-01-22 00:03:09', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (104,12, 'Spino-Eier', '2024-01-21 23:10:11', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (103,12, 'Test', '2024-01-21 20:34:09', 0, null, 0, null, 1);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (102,12, 'Statistics-Log incoming', '2024-01-21 23:55:09', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (101,12, 'Spino knuddeln', '2024-01-21 01:08:16', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (100,12, 'Knuddeln mit allen', '2024-01-20 23:05:16', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (35, 12, 'Epic Games free Games', '2024-02-01 20:00:36', 0, 10080, 1, '2024-02-08 20:00:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (3, 12, 'René hat keine Lust auf Tomaten, lol', '2023-08-09 22:45:43', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (5, 12, 'Overwatch 2 Invasion', '2023-08-10 20:00:43', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (10, 12, 'Reminder für Epic Games', '2023-08-17 20:06:14', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (11, 12, 'Replay', '2023-08-11 23:26:22', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (13, 12, 'Sons of the Forest', '2023-08-16 08:38:08', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (20, 12, 'Test für 0', '2023-08-13 00:57:22', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (21, 12, 'Test ohne 0', '2023-08-13 00:57:22', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (29, 12, 'neuer D.Va Overwatch Skin', '2023-08-17 02:10:14', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (30, 12, 'Denis gratulieren', '2023-08-16 23:49:14', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (31, 12, 'Test', '2023-08-17 23:59:14', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (32, 12, 'Testt', '2023-08-18 00:00:14', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (40, 12, 'The Crew Motorfest Demo downloaden', '2023-09-14 20:00:42', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (44, 12, 'Game Pass kündigen', '2023-09-30 20:00:32', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (69, 12, 'Anniversary für Rene-Tab', '2023-11-28 23:55:40', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (74, 12, 'Valorant Verbot aufgehobenn', '2023-12-19 20:00:16', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (73, 12, 'Overwatch Season 8', '2023-12-05 20:00:05', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (71, 12, 'GTA IV Trailer', '2023-12-05 15:00:04', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (70, 12, 'Sons of the Forest Full-Release', null, 0, null, 1, '2024-02-22 18:00:00', 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (45, 12, 'Handy von Steckdose', '2023-09-08 01:00:49', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (65, 12, 'Donowall melden', '2023-11-14 23:04:25', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (64, 12, 'Messer', '2023-11-10 23:30:42', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (59, 12, 'Ghost-Skin', '2023-10-29 21:45:33', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (51, 12, 'Cookie 24 Stunden testen', '2023-09-25 21:00:43', 0, null, 0, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (55, 12, 'Rene´s Felix-Timer um 23:59 anmachen', '2023-09-29 23:55:33', 0, null, 1, null, 0);
INSERT INTO beta.reminder (id, discord_user_id, content, sent_at, error, repeat_in_minutes, whatsapp, time_to_sent, is_timer) VALUES (62, 12, 'Titanfall 3', null, 0, null, 1, '2026-01-01 00:00:00', 0);
