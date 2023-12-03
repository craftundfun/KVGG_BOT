USE beta;

SELECT id FROM quest WHERE time_type = 'daily';

DELETE FROM quest_discord_mapping WHERE id IN (SELECT id FROM quest WHERE time_type = 'daily')

USE testproject;

SELECT q.*, qdm.* FROM quest q INNER JOIN quest_discord_mapping qdm ON q.id = qdm.quest_id ORDER BY qdm.time_created DESC