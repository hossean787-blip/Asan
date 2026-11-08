# -*- coding: utf-8 -*-
"""Create a consistent, verifiable SQLite snapshot (including uncheckpointed WAL)."""
import argparse
import datetime
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote


def backup_database(source, destination):
    source=Path(source).expanduser().resolve()
    destination=Path(destination).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError('فایل دیتابیس اصلی پیدا نشد.')
    if source==destination:
        raise ValueError('مسیر نسخه پشتیبان نمی‌تواند با فایل اصلی برابر باشد.')
    if destination.exists():
        raise FileExistsError('نسخه پشتیبان با این نام موجود است؛ فایل قبلی را بازنویسی نمی‌کنیم.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+'.partial')
    if temporary.exists():
        raise FileExistsError('فایل موقت قبلی وجود دارد؛ آن را ابتدا بررسی کنید.')
    try:
        source_db=sqlite3.connect('file:'+quote(source.as_posix(),safe='/:')+'?mode=ro',uri=True)
        target_db=sqlite3.connect(str(temporary))
        try:
            source_db.backup(target_db, pages=64)
        finally:
            target_db.close();source_db.close()
        check=sqlite3.connect(str(temporary))
        try:
            validity=check.execute('PRAGMA integrity_check').fetchone()[0]
            tables={x[0] for x in check.execute('SELECT name FROM sqlite_master WHERE type="table"')}
            if validity!='ok' or not {'exams','assignments','responses','settings'}.issubset(tables):
                raise RuntimeError('کنترل یکپارچگی نسخه پشتیبان ناموفق بود.')
            counts={name:check.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('exams','responses','custom_questions')}
        finally:
            check.close()
        if os.name!='nt':os.chmod(temporary,0o600)
        os.replace(str(temporary),str(destination))
        return {'path':str(destination),'size':destination.stat().st_size,'rows':counts,'integrity':'ok'}
    except Exception:
        if temporary.exists(): temporary.unlink()
        raise


def main():
    parser=argparse.ArgumentParser(description='پشتیبان امن دیتابیس اپ مصاحبه حسابداری')
    parser.add_argument('--db',default=str(Path(__file__).resolve().parent/'private_data'/'miz.sqlite3'))
    parser.add_argument('--output',default='')
    args=parser.parse_args()
    dest=args.output or str(Path(__file__).resolve().parent/'private_data'/'backups'/('miz-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3'))
    result=backup_database(args.db,dest)
    print('نسخه پشتیبان سالم ایجاد شد:',result['path'])
    print('حجم (بایت):',result['size'],'| تعداد جلسات:',result['rows']['exams'],'| پاسخ‌ها:',result['rows']['responses'])

if __name__=='__main__':main()