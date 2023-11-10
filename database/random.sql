USE beta;

SELECT id FROM quest WHERE time_type = 'daily';

DELETE FROM quest_discord_mapping WHERE id IN (SELECT id FROM quest WHERE time_type = 'daily')