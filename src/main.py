import argparse,json,os
from pathlib import Path
from .storage.database import Database
from .sources.broker_monitor import BrokerMonitor
from .sources.tradingcentral_monitor import monitor as monitor_announcements
from .reports.weekly_report import generate
from .reports.company_report import get_company_report
from .crawler.fetch import Fetcher
from .utils.logging import configure_logging
from .regulators.cysec import CURRENT_URL,FORMER_URL,DOMAINS_URL,parse_firms,parse_domains,attach_domains
from .regulators.registry import Registry
from .reports.registry_export import export_registry

def main(argv=None):
    parser=argparse.ArgumentParser(description='Acuity Competitor Intelligence V1')
    parser.add_argument('--db',default=os.getenv('ACI_DB_PATH','data/competitor_intelligence.db'))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init-db')
    brokers=sub.add_parser('scan-brokers'); brokers.add_argument('--fixture-dir')
    announcements=sub.add_parser('scan-announcements'); announcements.add_argument('--fixture')
    weekly=sub.add_parser('weekly-report'); weekly.add_argument('--output-dir',default='reports/output')
    company=sub.add_parser('company-report'); company.add_argument('company_id')
    regulator=sub.add_parser('scan-regulator'); regulator.add_argument('regulator_id',choices=['cysec'])
    regulator.add_argument('--current-fixture'); regulator.add_argument('--former-fixture'); regulator.add_argument('--domains-fixture')
    registry=sub.add_parser('registry-export'); registry.add_argument('--output',default='reports/output/broker-registry.csv')
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
    elif args.command=='scan-regulator':
        fetcher=Fetcher(os.getenv('ACI_USER_AGENT','AcuityCompetitorResearch/1.0'),float(os.getenv('ACI_REQUEST_INTERVAL_SECONDS','2')))
        def content(fixture,url): return Path(fixture).read_text(encoding='utf-8') if fixture else fetcher.get(url).text
        current_html=content(args.current_fixture,CURRENT_URL); former_html=content(args.former_fixture,FORMER_URL); domains_html=content(args.domains_fixture,DOMAINS_URL)
        domains=parse_domains(domains_html)
        current=attach_domains(parse_firms(current_html,source_url=CURRENT_URL),domains)
        former=parse_firms(former_html,former=True,source_url=FORMER_URL)
        snapshots=[('CURRENT',CURRENT_URL,current_html,len(current)),('FORMER',FORMER_URL,former_html,len(former)),('DOMAINS',DOMAINS_URL,domains_html,len(domains))]
        print(json.dumps(Registry(db).ingest(args.regulator_id,[*current,*former],snapshots),indent=2))
    elif args.command=='registry-export': print(export_registry(db,args.output))

if __name__=='__main__': main()

