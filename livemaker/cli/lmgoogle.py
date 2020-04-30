# -*- coding: utf-8
#
# Copyright (C) 2020 Stefan Berndt <stefan.berndt@imoriath.com>
#
# This file is a part of pylivemaker.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
"""LiveMaker google translation tool."""

import click
import sys
import requests
import csv
import time

def savecsv(csv_file, csv_data):
    with open(csv_file, "w", newline="\n") as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=",", quotechar="\"", quoting=csv.QUOTE_MINIMAL)
        for row in csv_data:
            csv_writer.writerow(row)
    print("CSV saved.")

@click.command()
@click.argument("csv_file" ,required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--from-lang", "-fl", required=False, type=str, default="ja", help="Original language (default:ja)")
@click.option("--to-lang", "-tl", required=False, type=str, default="en", help="Target language (default:en)")
@click.option("--from-column", "-fc", required=False, type=int, default=3, help="Original column number (start at 0,default:3)")
@click.option("--to-column", "-tc", required=False, type=int, default=4, help="Target column number (start at 0,default:4)")
@click.option("--delay", "-d", required=False, type=int, default=3000, help="Delay between translations in milliseconds."
              " If you set this too low, you might get an temporary IP ban (HTTP 429) from google! (default:3000)")
@click.option("--no-autosave", is_flag=True, default=False, help="Do not save the translations every 5 minutes.")
@click.option("--no-encodecheck", is_flag=True, default=False,
              help="Do not check the translation for cp932 encoding. Using this option may cause troubles on lmlsb later.")
def lmgoogle(csv_file, from_lang, to_lang, from_column, to_column, delay, no_autosave, no_encodecheck):

    csv_data = []

    save_time = time.time()

    # load the csv file
    with open(csv_file, newline="\n") as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        for row in csv_reader:
            csv_data.append(row)

    if from_lang == to_lang:
        sys.exit("Original and Target language must not be the same!")

    if from_column == to_column:
        sys.exit("Original and Target column must not be equal!")

    for row in csv_data:
        if len(row) <= from_column or len(row) <= to_column:
            continue # skip if row is too short
        if row[from_column] == "":
            continue # skip if source text is empty
        if row[to_column] != "":
            continue # skip if already translated

        from_text = row[from_column]

        # parameters got by network analyzing. I have no clue what the most of them are for.
        params = {"client":"t", "sl":from_lang, "tl":to_lang,
                "hl":"en","dt":"t","ie":"UTF-8","oe":"UTF-8","otf":"1","ssel":"0","tsel":"0","kc":"1","tk":"",
                "q":from_text}

        # Seems some google translating apps use this api, but it's not official documented.
        # So it's possible google changes or closes this api, and this program does not work anymore.
        r = requests.get("https://translate.google.com/translate_a/single", params=params)

        if r.status_code != requests.codes.ok:
            print("Failed request: HTTP {}".format(r.status_code))
            break # just break, not exit --> to save already done translations

        # get the translated text
        to_text = r.json()[0][0][0]

        # wait some time to avoid IP ban
        time.sleep(delay / 1000)

        if not no_encodecheck:
            # google sometimes translates to characters, who are not encode-able in cp932.
            # Replace some characters I already know
            to_text = to_text.replace("·", ".")
            to_text = to_text.replace("？", "?")
            to_text = to_text.replace("ö", "ue") # Incomprehensible that we still have to use this ugly workaround in 2020.
            to_text = to_text.replace("ä", "ae") # It was invented for mechanical typewriters about 100 years ago...
            to_text = to_text.replace("ü", "ue")
            to_text = to_text.replace("Ö", "Oe")
            to_text = to_text.replace("Ä", "Ae")
            to_text = to_text.replace("Ü", "Ue")
            to_text = to_text.replace("ß", "ss")

            # Test cp932 encoding, replace all troublesome characters
            try:
                to_text.encode("cp932")
            except UnicodeEncodeError:
                a = to_text
                to_text = ""
                for b in a:
                    try:
                        b.encode("cp932")
                        to_text = to_text + b
                    except UnicodeEncodeError:
                        to_text = to_text + "."
                print("Encoding problem: \"{}\" contains non-cp932 characters. Changed to \"{}\"".format(a, to_text))

        print("Translated \"{}\" to \"{}\"".format(from_text,to_text))

        # store the translation result in csv_data.
        # Some text lines may occour multiple times, so we store all matching.
        for row2 in csv_data:
            if len(row2) <= from_column or len(row2) <= to_column:
                continue
            if row2[from_column] == from_text:
                row2[to_column] = to_text

        # autosave the csv file
        if not no_autosave and save_time + 300 < time.time():
            savecsv(csv_file, csv_data)
            save_time = time.time()

    # finally save the csv again
    savecsv(csv_file, csv_data)

# required for standalone run
if __name__=="__main__":
    lmgoogle()

