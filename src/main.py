import argparse,json,os
from pathlib import Path
from .storage.database import Database
from .sources.broker_monitor import BrokerMonitor
from .sources.tradingcentral_monitor import monitor as monitor_announcements
from .reports.weekly_report import generate
from .reports.company_report import get_company_report
from .crawler.fetch import Fetcher
from .utils.logging import configure_logging

def main(argv=None):
    parser=argparse.ArgumentParser(description='Acuity Competitor Intelligence V1')
    parser.add_argument('--db',default=os.getenv('ACI_DB_PATH','data/competitor_intelligence.db'))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init-db')
    brokers=sub.add_parser('scan-brokers'); brokers.add_argument('--fixture-dir')
    announcements=sub.add_parser('scan-announcements'); announcements.add_argument('--fixture')
    weekly=sub.add_parser('weekly-report'); weekly.add_argument('--output-dir',default='reports/output')
    company=sub.add_parser('company-report'); company.add_argument('company_id')
    args=parser.parse_args(argv); configure_logging(); db=Database(args.db); db.migrate()
    if args.command=='init-db': print(f'Initialised {args.db}')
    elif args.command=='scan-brokers':
        fetcher=Fetcher(os.getenv('ACI_USER_AGENT','AcuityCompetitorResearch/1.0'),float(os.getenv('ACI_REQUEST_INTERVAL_SECONDS','2')))
        print(json.dumps(BrokerMonitor(db,os.getenv('ACI_CONFIG_DIR','config'),fetcher,int(os.getenv('ACI_MAX_PAGES_PER_BROKER','25'))).run(args.fixture_dir),indent=2))
    elif args.command=='scan-announcements':
        if args.fixture: html=Path(args.fixture).read_text(encoding='utf-8')
        else: html=Fetcher().get('https://www.tradingcentral.com/news').text
        print(json.dumps({'announcements_created':monitor_announcements(db,html)}))
    elif args.command=='weekly-report': print('\n'.join(map(str,generate(db,args.output_dir))))
    elif args.command=='company-report': print(json.dumps(get_company_report(db,args.company_id),indent=2))

if __name__=='__main__': main()

