from praytimes import PrayTimes
from datetime import date, time, timedelta, datetime
import concurrent.futures
import requests
import pytz
import json


class Timeline:
    PRAYER_NAMES = {
        "fajr": "Fajr",
        "sunrise": "Sunrise",
        "dhuhr": "Dhuhr",
        "asr": "Asr",
        "maghrib": "Maghrib",
        "isha": "Isha"
    }
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
    def push_pins_for_user(user, sync=False):
        if not user.timeline_token:
            # They're not timeline-enabled
            return
        # Push pins for yesterday, today, tomorrow
        # (15s total)
        pending_pins = []
        for x in range(-1, 2):
            pending_pins += Timeline._push_pins_for_date(user, date.today() + timedelta(days=x))

        if sync:
            # Wait until all our calls clear
            concurrent.futures.wait(pending_pins)
        else:
            return pending_pins

    def _push_pins_for_date(user, date):
        pt = PrayTimes()
        pt.setMethod(user.config["method"])
        pt.adjust({"asr": user.config["asr"]})
        loc = user.location
        if hasattr(loc, "keys"):
            loc = loc['coordinates']
        times = pt.getTimes(date, loc, 0, format="Float")
        for key in ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]:
            yield Timeline.executor.submit(Timeline._push_time_pin, user, key, datetime.combine(date, time()).replace(tzinfo=pytz.utc) + timedelta(hours=times[key]))

    def _push_time_pin(user, prayer, timestamp):
        pin_data = Timeline._generate_pin(user, prayer, timestamp)
        res = requests.put("https://timeline-api.getpebble.com/v1/user/pins/%s" % pin_data["id"],
                           data=json.dumps(pin_data),
                           headers={"X-User-Token": user.timeline_token, "Content-Type": "application/json"})
        assert res.status_code == 200, "Pin push failed %s %s" % (res, res.text)
        return True

    def _generate_pin(user, prayer, timestamp):
        pin_id = "%s:%s:%s" % (user.user_token, timestamp.date(), prayer)
        return {
            "id": pin_id,
            "time": timestamp.isoformat(),
            "layout": {
                "type": "genericPin",
                "title": Timeline.PRAYER_NAMES[prayer],
                "subtitle": "in %s" % user.location_geoname,
                "tinyIcon": "system://images/TIMELINE_SUN_TINY"
            }
        }
