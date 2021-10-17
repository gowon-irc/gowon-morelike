#!/usr/bin/env python

import json
import re
import random

import configargparse
import paho.mqtt.client as mqtt
import pronouncing
import pyphen

MODULE_NAME = "morelike"
h_en = pyphen.Pyphen(lang="en_US")


def trans_word(curr_word, sub_words=[], ignored_words=[]):
    sub_word_parts = {
        i: pronouncing.rhyming_part(pronouncing.phones_for_word(i)[0])
        for i in sub_words
    }
    # return if word is in ignored word lists
    if curr_word in ignored_words:
        return curr_word
    # return if more than one word is passed
    if " " in curr_word:
        return curr_word
    # strip non alphanumeric characters from word
    curr_word = "".join(i for i in curr_word if i.isalnum())
    # get the phonemes for the current word
    word_phone_list = pronouncing.phones_for_word(curr_word)
    # if no phonemes were found return the current word
    if not word_phone_list:
        return curr_word
    # pick the first pronunciation, it's usually accurate
    word_phones = word_phone_list[0]
    # if the number of syllables is 1, no need to use pyphen to split
    if pronouncing.syllable_count(word_phones) == 1:
        word_syllables = [curr_word]
    else:
        # use pyphen to split the word into syllables
        word_syllables = h_en.inserted(curr_word).split("-")
        # if the word couldn't be split, return the original word
        if not word_syllables:
            return curr_word
    # if pyphen's syllable count doesn't match pronouncing's, return the word
    if pronouncing.syllable_count(word_phones) != len(word_syllables):
        return curr_word
    # use any of our words that exist in the phoneme for the current word
    rep_words = [
        (i, sub_word_parts[i])
        for i in sub_word_parts
        if sub_word_parts[i] in word_phones
    ]
    # if no words match, return the current word
    if not rep_words:
        return curr_word
    # pick one of our matched words to be our new syllable
    new_syl, new_syl_pronounciation = random.choice(rep_words)
    # use regex to just find the vowel within our word's phoneme
    new_syl_vowel = re.search(r"(.*\d)", new_syl_pronounciation).group()
    # use regex to find the vowel of our phoneme within our current word
    syllable_index = re.findall(r"\w+\d", word_phones).index(new_syl_vowel)
    # if our new syllable ends with a vowel, keep the end of the original
    if re.search(r"[aeiouy]$", new_syl):
        new_syl += re.search(
            r"[^aeiouy]*$", word_syllables[syllable_index]
        ).group()
    # using the found index, replace the old syllable with the new one
    word_syllables[syllable_index] = new_syl

    # recombine and return
    out = "".join(word_syllables)
    return out


def morelike(line, sub_words, ignored_words):
    new_line = " ".join(
        trans_word(i, sub_words, ignored_words) for i in line.split()
    )

    return "{}? More like {}".format(line, new_line)


def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")

    client.subscribe("/gowon/input")


def gen_on_message_handler(sub_words, ignored_words):
    #  return morelike(line, sub_words, ignored_words)
    def f(client, userdata, msg):
        try:
            msg_in_json = json.loads(msg.payload.decode())
        except JSONDecodeError:
            print("Error parsing message json")
            return

        if msg_in_json["command"] == "morelike":
            out = morelike(msg_in_json["args"], sub_words, ignored_words)
            msg_out_json = {
                "module": MODULE_NAME,
                "msg": out,
                "nick": msg_in_json["nick"],
                "dest": msg_in_json["dest"],
                "comand": msg_in_json["command"],
                "args": msg_in_json["args"],
            }

            client.publish("/gowon/output", json.dumps(msg_out_json))

    return f


def main():
    print(f"{MODULE_NAME} starting")

    p = configargparse.ArgParser()
    p.add(
        "-H", "--broker-host", env_var="GOWON_BROKER_HOST", default="localhost"
    )
    p.add(
        "-P",
        "--broker-port",
        env_var="GOWON_BROKER_PORT",
        type=int,
        default=1883,
    )
    p.add(
        "-s",
        "--sub-words",
        action="append",
        env_var="GOWON_SUB_WORDS",
        default=[],
    )
    p.add(
        "-i",
        "--ignored-words",
        action="append",
        env_var="GOWON_IGNORED_WORDS",
        default=[],
    )
    opts = p.parse_args()

    sub_words = [j for i in opts.sub_words for j in i.split()]
    ignored_words = [j for i in opts.ignored_words for j in i.split()]

    client = mqtt.Client(f"gowon_{MODULE_NAME}")

    client.on_connect = on_connect
    client.on_message = gen_on_message_handler(sub_words, ignored_words)

    client.connect(opts.broker_host, opts.broker_port)

    client.loop_forever()


if __name__ == "__main__":
    main()
