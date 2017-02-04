#!/usr/bin/env python

import csv
import curses
import datetime
import glob
import os
import requests
import signal
import sys
import threading
import traceback

import display

SERVER_ADDRESS = "https://stuypulse-attendance.appspot.com"
ADMIN_EMAIL = ""
ADMIN_PASSWORD = ""
OFFLINE = False
OUTPUT_FILE = "OUT"

today = datetime.datetime.now()
MONTH = today.month
DAY = today.day
YEAR = today.year

LOG_DIR = "logs/"
LOG_FORMAT = "%02d-%02d-%04d.log"
LOG = LOG_DIR + LOG_FORMAT % (MONTH, DAY, YEAR)
LOG_FAILED = LOG + ".FAILED"

STUDENT_DATA = {}

file_lock = threading.Lock()

def cleanup(signal, frame):
    display.close()
    sys.exit(0)

def append_log(s, log):
    file_lock.acquire()
    with open(log, "a") as f:
        f.write("%s\n" % s)
    file_lock.release()

def set_log_names():
    global LOG, FAILED_LOG
    LOG = LOG_DIR + LOG_FORMAT % (MONTH, DAY, YEAR)
    FAILED_LOG = LOG + ".FAILED"

def get_date_from_log(log):
    log = log[:log.find(".")]
    if "/" in log:
        log = log[log.rfind("/")+1:]
    month, day, year = map(int, log.split("-"))
    return month, day, year

def format_date(month, day, year):
    date = datetime.datetime(year, month, day)
    return date.strftime("%B %d, %Y")

def login():
    global ADMIN_EMAIL, ADMIN_PASSWORD

    email = display.get_input(prompt="Administrator Email: ")
    password = display.get_input(prompt="Administrator Password: ", hidden=True)
    now = datetime.datetime.now()
    data = {
        "email": email,
        "pass": password,
        "month": now.month,
        "day": now.day,
        "year": now.year
    }

    response = send_request("/", data=data)
    if "SUCCESS" in response:
        display.add_message(response, color=display.GREEN)
        ADMIN_EMAIL = email
        ADMIN_PASSWORD = password
        return True

    display.add_message(response, color=display.RED)
    return False

def already_scanned(osis):
    log = LOG_DIR + LOG_FORMAT % (MONTH, DAY, YEAR)
    if os.path.exists(log):
        return osis in [int(x) for x in open(log, "r").readlines()]
    else:
        return False

def load_student_data():
    if not os.path.exists("STUDENTS.csv"):
        dump_csv(out="STUDENTS.csv")

    csv_reader = csv.reader(open("STUDENTS.csv", "r"))
    csv_reader.next()
    for row in csv_reader:
        _id = row[0]
        name = row[1]
        STUDENT_DATA[name] = int(_id)

def menu():
    if OFFLINE:
        color = display.RED
    else:
        color = 0

    display.add_message("1)  Take attendance for today")
    display.add_message("2)  Take attendance for a specific day")
    display.add_message("3)  Show all attendance data", color=color)
    display.add_message("4)  Show attendance data for a specific day", color=color)
    display.add_message("5)  Show attendance data for today", color=color)
    display.add_message("6)  Show attendance data for a student", color=color)
    display.add_message("7)  Export all data to CSV", color=color)
    display.add_message("8)  Export data to CSV for a specific month", color=color)
    display.add_message("9)  Delete attendance for a student on a particular day", color=color)
    display.add_message("10) Drop(delete) all attendance data", color=color)
    display.add_message("11) Upload all failed ids", color=color)
    display.add_message("12) Get percentage of meetings attended by a student", color=color)
    display.add_message("13) Go online")
    display.add_message("14) Exit\n")
    choice = display.get_number(prompt="What would you like to do?> ")
    return choice

def scan():
    load_student_data()
    set_log_names()
    display.add_message("Enter \"back\" to go back", color=display.YELLOW)

    while True:
        _input = display.get_input(prompt="Enter name or id: ")
        try:
            # Scan by id
            _input = int(_input)
            if len(str(_input)) != 9:
                display.add_message("Invalid barcode", color=display.RED)
                continue
            osis = _input

            if already_scanned(osis):
                display.add_message("%d already scanned in" % osis, color=display.YELLOW)
                continue
            else:
                display.add_message("Got barcode: %d" % osis, color=display.GREEN)
        except ValueError:
            if _input == "back":
                return

            # Scan by name
            candidates = [(name, osis) for name, osis in STUDENT_DATA.iteritems() if name.lower().startswith(_input)]
            num_candidates = len(candidates)
            if num_candidates == 0:
                display.add_message("Student not found", color=display.RED)
                continue
            elif num_candidates == 1:
                osis = int(candidates[0][1])
                name = candidates[0][0]
            else:
                display.add_message("Multiple candidates found: ", color=display.YELLOW)
                index = 1
                for candidate in candidates:
                    display.add_message("[%d] %s" % (index, candidate[0]))
                    index += 1
                choice = display.get_number("[1-%d] " % (index-1))
                if not (1 <= choice <= index-1):
                    display.add_message("Invalid selection", color=display.RED)
                    continue
                osis = int(candidates[choice-1][1])
                name = candidates[choice-1][0]

            if already_scanned(osis):
                display.add_message("%s already scanned in" % name, color=display.YELLOW)
                continue
            else:
                display.add_message("Got %s - %d" % (name, osis), color=display.GREEN)

        thread = threading.Thread(target=post_osis, args=[osis])
        thread.start()

def handle_response(response, out=OUTPUT_FILE, save=False):
    if len(response) == 0:
        display.add_message("ERROR: Could not contact server", color=display.RED)
    elif "ERROR" in response:
        display.add_message(response, color=display.RED)
    else:
        if save:
            f = open(out, "w")
            f.write(response)
            f.close()
            display.add_message("Output saved to file %s" % out, color=display.GREEN)
        else:
            display.add_message(response, color=display.GREEN)

def dump_data(out=OUTPUT_FILE):
    response = send_request("/dump", data={})
    handle_response(response, file=out, save=True)

def dump_day(month, day, year):
    data = {
        "month": month,
        "day": day,
        "year": year
    }
    response = send_request("/day", data)
    handle_response(response, file=OUTPUT_FILE, save=True)

def dump_today():
    today = datetime.datetime.now()
    dump_day(today.month, today.day, today.year)

def dump_student(osis):
    data = {
        "id": osis
    }
    response = send_request("/student", data)
    handle_response(response, file="%s.log" % osis, save=True)

def delete_date(osis, month, day, year):
    data = {
        "month": month,
        "day": day,
        "year": year,
        "id": osis
    }
    response = send_request("/delete", data)
    handle_response(response)

def dump_csv(month=None, out=OUTPUT_FILE + ".csv"):
    data = {}
    if month:
        data["month"] = month
    response = send_request("/csv", data)
    handle_response(response, file=out, save=True)

def drop_database():
    response = send_request("/dropdb", {})
    handle_response(response)

def post_osis(osis):
    if OFFLINE:
        append_log(osis, LOG_FAILED)
        return

    data = {
        "id": osis,
        "month": MONTH,
        "day": DAY,
        "year": YEAR
    }
    response = send_request("/", data)
    if len(response) == 0:
        display.add_message("ERROR: Could not contact server", color=display.RED)
        append_log(osis, LOG_FAILED)
    elif "ERROR" in response:
        display.add_message(response, color=display.RED)
    else:
        append_log(osis, LOG)
        # Most recent attempt was successful, so we can assume that we are online
        upload_failed_ids(LOG)

def upload_failed_ids(log):
    failed_log = log + ".FAILED"
    failed_log_lock = failed_log + ".lock"
    if os.path.exists(failed_log_lock):
        return

    if not os.path.exists(failed_log):
        return

    with open(failed_log, "r") as f:
        failed_osises = [int(l) for l in f.readlines()]

    if len(failed_osises) > 0:
        # Create lock file
        open(failed_log_lock, "a").close()

        month, day, year = get_date_from_log(log)
        date = format_date(month, day, year)

        display.add_message("Preparing to upload pending IDs (%s)" % date, color=display.MAGENTA)
        data = {
            "month": month,
            "day": day,
            "year": year
        }
        for osis in failed_osises:
            data["id"] = osis
            response = send_request("/", data)
            if len(response) == 0:
                append_log(osis, failed_log + ".new")
            else:
                append_log(osis, log)
        if os.path.exists(failed_log + ".new"):
            display.add_message("Failed to upload all pending IDs (%s)" % date, color=display.YELLOW)
            os.rename(failed_log + ".new", failed_log)
        else:
            display.add_message("Successfully uploaded all pending IDs (%s)" % date, color=display.GREEN)
            os.remove(failed_log)
        os.remove(failed_log_lock)

def upload_all_failed_ids():
    logs = glob.glob(LOG_DIR + "*.FAILED")
    if len(logs) == 0:
        display.add_message("There are no pending IDs", color=display.YELLOW)
        return

    display.add_message("Preparing to upload all pending IDs to the server!", color=display.MAGENTA)
    for log in logs:
        upload_failed_ids(log)

def get_student_percentage(osis):
    data = {
        "id": osis
    }
    response = send_request("/percent", data)
    handle_response(response)

def send_request(path, data):
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        data["email"] = ADMIN_EMAIL
        data["pass"] = ADMIN_PASSWORD
    try:
        response = requests.post(SERVER_ADDRESS + path, data=data)
    except:
        return ""
    return response.text.strip()

def main():
    global OFFLINE
    while True:
        try:
            choice = menu()
            if choice == 1:
                today = datetime.datetime.now()
                MONTH = today.month
                DAY = today.day
                YEAR = today.year
                scan()
            elif choice == 2:
                MONTH = display.get_number(prompt="Month (1-12): ")
                DAY = display.get_number(prompt="Day (1-31): ")
                YEAR = display.get_number(prompt="Year (####): ")
                try:
                    datetime.datetime(YEAR, MONTH, DAY)
                except:
                    display.add_message("Invalid date", color=display.RED)
                    continue
                scan()
            elif choice == 3 and not OFFLINE:
                dump_data()
            elif choice == 4 and not OFFLINE:
                month = display.get_number(prompt="Month (1-12): ")
                day = display.get_number(prompt="Day (1-31): ")
                year = display.get_number(prompt="Year (####): ")
                try:
                    datetime.datetime(year, month, day)
                except:
                    display.add_message("Invalid date", color=display.RED)
                    continue
                dump_day(month, day, year)
            elif choice == 5 and not OFFLINE:
                dump_today()
            elif choice == 6 and not OFFLINE:
                osis = display.get_number(prompt="Student's ID: ")
                dump_student(osis)
            elif choice == 7 and not OFFLINE:
                dump_csv()
            elif choice == 8 and not OFFLINE:
                month = display.get_number(prompt="Month to format (1-12): ")
                dump_csv(month=month)
            elif choice == 9 and not OFFLINE:
                osis = display.get_number(prompt="Student's ID: ")
                month = display.get_number(prompt="Month (1-12): ")
                day = display.get_number(prompt="Day (1-31): ")
                year = display.get_number(prompt="Year (####): ")
                delete_date(osis, month, day, year)
            elif choice == 10 and not OFFLINE:
                confirm = display.get_input(prompt="Are you sure you want to delete all the data? (y/n) ")
                if confirm.lower() == "y":
                    display.add_message("Clearing the database...", color=display.YELLOW)
                    drop_database()
                else:
                    display.add_message("Aborting", color=display.RED)
            elif choice == 11 and not OFFLINE:
                upload_all_failed_ids()
            elif choice == 12 and not OFFLINE:
                osis = display.get_number(prompt="Student's ID: ")
                get_student_percentage(osis)
            elif choice == 13:
                if OFFLINE:
                    login()
                    if ADMIN_PASSWORD:
                        OFFLINE = False
                else:
                    display.add_message("You are already online", color=display.YELLOW)
            elif choice == 14:
                return
            elif OFFLINE:
                options = "You are currently in offline mode. available options are:\n\n"
                options += "1)  Take attendance for today\n"
                options += "2)  Take attendance for a specific day\n"
                options += "13) Go online\n"
                options += "14) Exit\n\n"
                options += "For more functionality, re-run the program or choose option 13\n"
                display.add_message(options, color=display.YELLOW)
            else:
                display.add_message("Invalid choice.", color=display.RED)
        except:
            error = traceback.format_exc()
            append_log(error, "error.log")
            display.add_message("Something went wrong!", color=display.RED)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)

    stdscr = curses.initscr()
    display = display.ScannerDisplay(stdscr)

    if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)

    if "--offline" in sys.argv:
        OFFLINE = True
        display.add_message("Running in offline mode", color=display.YELLOW)

    while not OFFLINE and not login():
        pass

    main()
    cleanup()
