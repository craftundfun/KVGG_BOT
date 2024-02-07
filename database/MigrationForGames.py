from src.Services.Database import Database


def main():
    database = Database()
    getUsersQuery = "SELECT id FROM discord"
    users = database.fetchAllResults(getUsersQuery)
    getGameQuery = "SELECT id FROM discord_game"
    games = database.fetchAllResults(getGameQuery)

    getGameQuery = "SELECT * FROM game_discord_mapping WHERE discord_id = %s AND discord_game_id = %s"
    deleteQuery = "DELETE FROM game_discord_mapping WHERE id = %s"
    insertQuery = ("INSERT INTO game_discord_mapping (discord_id, discord_game_id, time_played_online, "
                   "time_played_offline, while_online) VALUES (%s, %s, %s, %s, %s)")

    for user in users:
        print(f"[INFO] checking games for user-id: {user['id']}")

        for game in games:
            print(f"[INFO] checking game-id: {game['game_id']}")
            gameMappings = database.fetchAllResults(getGameQuery, (user['id'], game['id'],))

            if not gameMappings:
                print(f"[INFO] game-mapping does not exist for user-id")
                continue

            onlineValue = 0
            offlineValue = 0

            for gameMapping in gameMappings:
                if gameMapping['while_online']:
                    onlineValue += gameMapping['time_played']
                else:
                    offlineValue += gameMapping['time_played']

                if not database.runQueryOnDatabase(deleteQuery, (gameMapping['id'],)):
                    print(f"[ERROR] couldn't delete data for user-id: {user['id']} and game-id: {game['id']}")

            print(f"[INFO] calculated online value: {onlineValue}, offline value: {offlineValue}")

            if not database.runQueryOnDatabase(insertQuery,
                                               (user['id'], game['id'], onlineValue, offlineValue, True,)):
                print(f"[ERROR] couldn't insert data for user-id: {user['id']} and game-id: {game['id']}")


if __name__ == "__main__":
    main()
