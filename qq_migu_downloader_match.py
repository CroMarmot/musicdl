#!/usr/bin/env python
from dataclasses import dataclass
import logging
import os
from typing import Any, Dict, List, Tuple
import csv

import click

from musicdl import musicdl
from musicdl.modules.utils.logger import colorize, printTable

CSV_HEAD = ['singer', 'title', 'source']


@dataclass
class Song:
    source: str
    songid: str
    singers: str
    album: str
    songname: str
    savedir: str
    savename: str
    download_url: str
    lyric: str
    filesize: str
    ext: str
    duration: str


def manual_pick(l: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # make table
    table_title = ['序号', '歌手', '歌名', '大小', '时长', '专辑', '来源']
    items, records, idx = [], {}, 0
    for value in l:
        items.append([
            colorize(str(idx), 'number'),
            colorize(value['singers'], 'singer'),
            value['songname'],
            value['filesize'] if value['ext'] != 'flac' else colorize(
                value['filesize'], 'flac'),
            value['duration'],
            value['album'],
            colorize(value['source'].upper(), 'highlight'),
        ])
        records.update({str(idx): value})
        idx += 1
    printTable(table_title, items)
    ipt = input("pick number(q for quit):")
    try:
        i = int(ipt)
        if i >= 0 and i < len(l):
            return i
    except:
        return -1
    return -1


def qq_migu_download(singer: str, title: str, folder: str,
                     **kwargs) -> Tuple[List[Song], List[Song]]:
    config = {
        'logfilepath':
        kwargs['logfilepath'] if 'logfilepath' in kwargs else 'musicdl.log',
        'savedir': folder,
        'search_size_per_source': 5,
        'proxies': {}
    }
    target_srcs = ['migu', 'qqmusic']  # 'qqmusic'
    target_srcs = [
        # 'kugou', api全是试听
        # 'kuwo', api炸了 下不了歌 全是“请在手机播放”
        'qqmusic',
        # 'qianqian',
        'fivesing',
        'netease',
        'migu',
        'joox',
        'yiting',
    ]
    client = musicdl.musicdl(config=config)
    result_dict = client.search(f"{singer} {title}", target_srcs=target_srcs)
    # result_list: List[Song] = []
    result_list: List[Dict[str, str]] = []
    for songlist in result_dict.values():
        for item in songlist:
            # result_list.append(Song(**item))
            result_list.append(item)

    # def matched(s: Song):
    #     return s.singers == singer and s.songname == title
    def matched(s: Dict[str, str]) -> bool:
        return s['singers'] == singer and s['songname'] == title

    def similar_singer(s: Dict[str, str]) -> bool:
        # 模糊 singer
        # 大小写与包含关系
        if s['singers'].upper() in singer.upper() or singer.upper(
        ) in s['singers'].upper():
            return True
        # 可能是多个合作, 顺序不同， 或者分割符号不同
        splitchars = [',', '/']
        for splitleft in splitchars:
            for splitright in splitchars:
                if sorted(s['singers'].upper().split(splitleft)) == sorted(
                        singer.upper().split(splitright)):
                    return True
        return False

    def similar_songname(s: Dict[str, str]) -> bool:
        # 模糊，例如大小写，加括号的问题
        return s['songname'].upper() in title.upper() or title.upper(
        ) in s['songname'].upper()

    def matched_likely(s: Dict[str, str]):
        return similar_singer(s) and similar_songname(s)

    matched_list = [s for s in result_list if matched(s)]
    manualidx = -1
    if len(matched_list) == 0:  # 精确匹配, 未匹配到
        matched_list = [s for s in result_list if matched_likely(s)]
        if len(matched_list) > 2:
            print("Too much matched")
            # 过多匹配 可能各种不同Remix, 不如不匹配
            matched_list = []
        if len(matched_list) == 0 and 'manual' in kwargs and kwargs['manual']:
            manualidx = manual_pick(result_list)
            if manualidx >= 0:
                matched_list = [result_list[manualidx]]

    for item in matched_list:
        item['savename'] = f"{item['singers']} - {item['songname']}"

    success_list: List[Song] = []

    table_title = [
        '序号', '歌手', '歌名', '大小', '时长', '专辑', '来源', '完全匹配', '模糊匹配', '手动匹配'
    ]
    items, records = [], {}
    for idx, value in enumerate(result_list):
        items.append([
            colorize(str(idx), 'number'),
            colorize(value['singers'], 'singer'),
            value['songname'],
            value['filesize'] if value['ext'] != 'flac' else colorize(
                value['filesize'], 'flac'),
            value['duration'],
            value['album'],
            colorize(value['source'].upper(), 'highlight'),
            matched(value),
            matched_likely(value),
            idx == manualidx,
        ])
        records.update({str(idx): value})
    printTable(table_title, items)

    if kwargs['dry']:
        return [], matched_list
    else:
        success_list = client.download(matched_list)
        for item in success_list:
            try:
                lrc = item['lyric'] # lrc可能是dict?
                if not lrc: continue
                with open(
                        os.path.join(
                            folder, f"{item['singers']} - {item['songname']}.lrc"),
                        'w') as lrcfile:
                    if not isinstance(lrc, str):
                        lrc = '\r'.join(lrc)
                    lrcfile.write(lrc)
            except Exception as e:
                logging.exception(e)

    return success_list, matched_list


@click.group()
def main():
    pass


@main.command('down')
@click.version_option()
@click.argument('singer')
@click.argument('title')
@click.option('-l', '--logfilepath', default='musicdl.log', help='日志文件保存的路径')
@click.option('-s', '--savedir', default='downloaded', help='下载的音乐保存路径')
@click.option('--dry-run',
              'dry_run',
              default=False,
              is_flag=True,
              help='不实际下载')
@click.option('--manual',
              default=False,
              is_flag=True,
              help='当完全匹配和模糊匹配都失效时是否采取手动匹配')
# @click.option('-c', '--count', default='5', help='在各个平台搜索时的歌曲搜索数量')
# @click.option('-t', '--targets', default=None, help='指定音乐搜索的平台, 例如"migu,joox"')
def single_down(singer, title, logfilepath, savedir, dry_run, manual):
    """
        搜索并精确匹配和和下载
        Examples:

        ./qq_migu_downloader_match.py csvdown --dry-run csvfile.csv
        ./qq_migu_downloader_match.py csvdown csvfile.csv -s /tmp/savedir
    """
    if not os.path.exists(savedir): os.makedirs(savedir)
    qq_migu_download(singer,
                     title,
                     savedir,
                     dry=dry_run,
                     logfilepath=logfilepath,
                     manual=manual)


@main.command('csvdown')
@click.version_option()
@click.argument('csvpath')
@click.option('-l', '--logfilepath', default='musicdl.log', help='日志文件保存的路径')
@click.option('-s', '--savedir', default='downloaded', help='下载的音乐保存路径')
@click.option('--ok-csv', 'ok_csv', default='ok.csv', help='成功下载列表')
@click.option('--skip-csv', 'skip_csv', default='skip.csv', help='跳过下载列表')
@click.option('--failed-csv',
              'failed_csv',
              default='failed.csv',
              help='失败下载列表')
@click.option('--dry-run',
              'dry_run',
              default=False,
              is_flag=True,
              help='不实际下载')
@click.option('--manual',
              default=False,
              is_flag=True,
              help='当完全匹配和模糊匹配都失效时是否采取手动匹配')
# @click.option('-c', '--count', default='5', help='在各个平台搜索时的歌曲搜索数量')
# @click.option('-t', '--targets', default=None, help='指定音乐搜索的平台, 例如"migu,joox"')
def csv_down(csvpath, logfilepath, savedir, dry_run, ok_csv, skip_csv,
             failed_csv, manual):
    """
        搜索并精确匹配和和下载
        Examples:

        ./qq_migu_downloader_match.py down --dry-run 周杰伦 一路向北
        ./qq_migu_downloader_match.py down 周杰伦 一路向北
    """
    if not os.path.exists(savedir): os.makedirs(savedir)

    ok_list = [CSV_HEAD]
    skip_list = [CSV_HEAD]
    failed_list = [CSV_HEAD]

    singer_titile_list = []
    with open(csvpath, 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # head
        for row in reader:
            singer = row[0]
            title = row[1]
            singer_titile_list.append([singer, title])

    for i, row in enumerate(singer_titile_list, start=1):
        singer, title = row
        print(f"{i}/{len(singer_titile_list)} {singer} - {title}")
        filename = os.path.join(savedir, f"{singer} - {title}")
        if os.path.isfile(filename + ".flac") or os.path.isfile(
                filename + ".mp3") or os.path.isfile(filename + ".m4a"):
            skip_list.append([singer, title, ''])
            continue
        success_list, matched_list = qq_migu_download(singer,
                                                      title,
                                                      savedir,
                                                      dry=dry_run,
                                                      logfilepath=logfilepath,
                                                      manual=manual)
        if len(success_list):
            # 可能模糊匹配，取实际搜索到的名字
            for o in success_list:
                ok_list.append([o['singers'], o['songname'], o['source']])
        else:
            failed_list.append([singer, title, ''])

    def dump_csv(data, filepath):
        writer = csv.writer(open(filepath, 'w'))
        writer.writerows(data)

    if not dry_run:
        if len(ok_list) > 1: dump_csv(ok_list, ok_csv)
        if len(skip_list) > 1: dump_csv(skip_list, skip_csv)
        if len(failed_list) > 1: dump_csv(failed_list, failed_csv)


if __name__ == '__main__':
    main()
