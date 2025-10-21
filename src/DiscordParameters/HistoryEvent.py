from enum import Enum


class HistoryEvent(Enum):
    JOIN_VOICE_CHANNEL = "join_voice_channel"
    LEAVE_VOICE_CHANNEL = "leave_voice_channel"
    SWITCH_VOICE_CHANNEL = "switch_voice_channel"

    START_STREAMING = "start_streaming"
    STOP_STREAMING = "stop_streaming"
    START_WEBCAM = "start_webcam"
    STOP_WEBCAM = "stop_webcam"

    MUTE_SELF = "mute_self"
    UNMUTE_SELF = "unmute_self"

    DEAFEN_SELF = "deafen_self"
    UNDEAFEN_SELF = "undeafen_self"

    MUTE_SERVER = "mute_server"
    UNMUTE_SERVER = "unmute_server"

    DEAFEN_SERVER = "deafen_server"
    UNDEAFEN_SERVER = "undeafen_server"

    START_ACTIVITY = "start_activity"
    STOP_ACTIVITY = "stop_activity"

    STATUS_ONLINE = "status_online"
    STATUS_IDLE = "status_idle"
    STATUS_DND = "status_dnd"
    STATUS_OFFLINE = "status_offline"
