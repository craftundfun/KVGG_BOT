from enum import Enum


def getValues() -> set:
    return set(channel.value for channel in ChannelIdUniversityTracking)


class ChannelIdUniversityTracking(Enum):
    UNI_1 = '803322264056496158'

    UNI_2 = '803322289339760651'

    UNI_3 = '901079103803904070'

    UNI_4 = '901079298801270796'

    UNI_5 = '927763854266601492'

    UNI_6_AMERICA = '927763900643049583'
