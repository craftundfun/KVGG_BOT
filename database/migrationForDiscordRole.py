import sys

from discord import Client

from src.Entities.Role.Repository.DiscordRoleRepository import getDiscordRoleMapping
from src.Manager.DatabaseManager import getSession


def migration(client: Client):
    if not (session := getSession()):
        print("[ERROR] couldn't get session")

        sys.exit(1)

    for member in client.get_all_members():
        if member.bot:
            print("[INFO] skipped {member.display_name}")

            continue

        for role in member.roles:
            print(f"[INFO] {member.display_name} has role {role.name}")

            if not (getDiscordRoleMapping(role, member, session)):
                print(f"[ERROR] couldn't fetch DiscordRoleMapping for {role} and {member}")
            else:
                print(f"[INFO] successfully fetched DiscordRoleMapping for {role} and {member}")

    sys.exit(0)
