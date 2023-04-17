SECONDS_IN_A_MINUTE = 60
SECONDS_IN_A_HOUR = 3600
SECONDS_IN_A_DAY = 86400

class UnableToParseError(Exception):
    pass

def parse_timestamp(timestamp: str):
    try:
        return int(timestamp)
    except ValueError:
        return parse_colon_timestamp(timestamp)

def parse_colon_timestamp(timestamp: str):
    if ":" not in timestamp:
        raise UnableToParseError("Unsupported time format.")
    
    else:
        time_parts = timestamp.split(":")
        try:
            time_parts_conv = [int(i) for i in time_parts]
        except TypeError:
            raise UnableToParseError("Invalid time input.")
        
        if len(time_parts_conv) == 2:
            minutes, seconds = time_parts_conv
            return minutes * SECONDS_IN_A_MINUTE + seconds
        
        elif len(time_parts_conv) == 3:
            hours, minutes, seconds = time_parts_conv
            return hours * SECONDS_IN_A_HOUR + minutes * SECONDS_IN_A_MINUTE + seconds
        
        elif len(time_parts_conv) == 4:
            days, hours, minutes, seconds = time_parts_conv
            return days * SECONDS_IN_A_DAY + hours * SECONDS_IN_A_HOUR + minutes * SECONDS_IN_A_MINUTE + seconds
        
        else:
            raise UnableToParseError("Unsupported time input. Supported time inputs are either in seconds or in colons (up to days).")
        

def parse_to_timestamp(time_seconds: int):
    if time_seconds < SECONDS_IN_A_MINUTE:
        if time_seconds < 10:
            time_seconds = f"0{time_seconds}"
        return f"0:{time_seconds}"
    elif time_seconds < SECONDS_IN_A_HOUR:
        return parse_seconds_to_minutes(time_seconds)
    elif time_seconds < SECONDS_IN_A_DAY:
        return parse_seconds_to_hours(time_seconds)
    else:
        return parse_seconds_to_days(time_seconds)

def parse_seconds_to_minutes(seconds: int):
    minutes = int(seconds / SECONDS_IN_A_MINUTE)
    remainder = seconds - minutes * SECONDS_IN_A_MINUTE

    if minutes < 10:
        minutes = f"0{minutes}"
    if remainder < 10:
        remainder = f"0{remainder}"
    return f"{minutes}:{remainder}"

def parse_seconds_to_hours(seconds: int):
    hours = int(seconds / SECONDS_IN_A_HOUR)
    remainder = seconds - hours * SECONDS_IN_A_HOUR

    if hours < 10:
        hours = f"0{hours}"
    return f"{hours}:{parse_seconds_to_minutes(remainder)}"

def parse_seconds_to_days(seconds: int):
    days = int(seconds / SECONDS_IN_A_DAY)
    remainder = seconds - days * SECONDS_IN_A_DAY

    return f"{days}:{parse_seconds_to_hours(remainder)}"

if __name__ == "__main__":
    print(parse_to_timestamp(10))
    print(parse_to_timestamp(100))
    print(parse_to_timestamp(10000))
    print(parse_to_timestamp(100000))