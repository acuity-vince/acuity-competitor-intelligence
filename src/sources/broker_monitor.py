import logging
from pathlib import Path
import yaml
from ..crawler.extract import extract_page
from ..crawler.fetch import Fetcher
from ..crawler.robots import parse_robots, may_fetch, robots_url
from ..crawler.sitemap import COMMON_SITEMAPS, parse_sitemap
from ..crawler.discovery import rank_urls
from ..detectors.competitor_detector import detect
from ..detectors.page_change_detector import relevant_change
from ..classifiers.evidence_classifier import classify
from ..scoring.confidence import score as confidence_score
from ..scoring.priority import score as priority_score
from ..utils.dates import utc_now
from ..utils.hashing import sha256

LOG=logging.getLogger(__name__)

def load_yaml(path):
    with open(path,encoding='utf-8') as f: return yaml.safe_load(f)

class BrokerMonitor:
    def __init__(self, db, config_dir='config', fetcher=None, max_pages=25):
        self.db=db; self.config_dir=Path(config_dir); self.fetcher=fetcher or Fetcher(); self.max_pages=max_pages
        self.competitor=load_yaml(self.config_dir/'competitors.yaml')['competitors'][0]
        self.products=load_yaml(self.config_dir/'products.yaml')['products']
        self.discovery_terms=load_yaml(self.config_dir/'search_terms.yaml')['discovery_terms']
        self.change_terms=[*self.competitor['aliases'],self.competitor['domain'],*(p['product_name'] for p in self.products)]

    def run(self, fixture_dir=None):
        brokers=load_yaml(self.config_dir/'brokers.yaml')['brokers']; run_id=self.db.start_run('BROKER_SCAN')
        counts={'companies':0,'pages':0,'errors':0,'signals':0}
        for broker in brokers:
            if not broker.get('active',True) and fixture_dir is None: continue
            self.db.upsert_company(broker); counts['companies']+=1
            for url,status,html in self._pages(broker,fixture_dir):
                if status!=200:
                    self.db.record_failure(broker['id'],url,status); counts['errors']+=1; continue
                counts['pages']+=1; counts['signals']+=self.process_page(broker,url,html)
        self.db.finish_run(run_id,**counts); return counts

    def _pages(self,broker,fixture_dir):
        if fixture_dir:
            path=Path(fixture_dir)/f"{broker['id']}.html"
            if path.exists(): yield broker['known_research_urls'][0],200,path.read_text(encoding='utf-8')
            return
        domain=broker['domain']; parser=None; candidates=list(broker.get('known_research_urls',[]))
        try:
            rr=self.fetcher.get(robots_url(domain)); parser=parse_robots(rr.text,f"https://{domain}") if rr.status_code==200 else None
            for suffix in COMMON_SITEMAPS:
                sr=self.fetcher.get(f"https://{domain}{suffix}")
                if sr.status_code==200: candidates.extend(parse_sitemap(sr.text))
        except Exception as exc: LOG.warning("Discovery failed for %s: %s",domain,exc)
        for url in rank_urls(candidates,domain,self.discovery_terms,self.max_pages):
            if parser and not may_fetch(parser,url):
                yield url,403,""; continue
            try:
                response=self.fetcher.get(url); yield str(response.url),response.status_code,response.text
            except Exception as exc:
                LOG.warning("Fetch failed for %s: %s",url,exc); yield url,0,""

    def process_page(self,broker,url,html):
        text,links,_=extract_page(html); result=detect(text,url,links,self.competitor['aliases'],self.products)
        previous=self.db.get_page(url); prior_text=previous['current_text'] if previous else ''
        change=relevant_change(prior_text,text,self.change_terms) if previous else {'changed':True,'relevant':bool(result.matched_terms),'added':text,'removed':''}
        self.db.save_page(broker['id'],url,200,sha256(html),sha256(text.lower()),text,change['relevant'])
        if not result.matched_terms:
            return self._possible_removal(broker,url,previous,change)
        classification=classify(result); conf=confidence_score('broker_explicit_access',classification['classification'])
        now=utc_now(); evidence=result.evidence[0] if result.evidence else f"Trading Central domain reference found at {url}."
        product_ids=result.products or (None,)
        for product_id in product_ids:
            self.db.add_evidence({'company_id':broker['id'],'competitor_id':'trading_central','product_id':product_id,'source_url':url,'source_type':'broker_website','evidence_text':evidence,'detected_at':now,'last_verified':now,'status':classification['classification'],'confidence_score':conf,'evidence_hash':sha256(broker['id']+url+str(product_id)+evidence)})
        if previous is None:
            kind='BROKER_TC_NEWLY_DETECTED'; return self._signal(broker,url,kind,evidence,conf,None,text)
        return 0

    def _possible_removal(self,broker,url,previous,change):
        pending=self.db.connection.execute("SELECT * FROM signals WHERE company_id=? AND source_url=? AND signal_type='POSSIBLE_REMOVAL' ORDER BY id DESC LIMIT 1",(broker['id'],url)).fetchone()
        wording="Trading Central references previously detected on the broker website are no longer present."
        if pending:
            self.db.connection.execute("UPDATE signals SET signal_type='BROKER_TC_REFERENCE_REMOVED',title='Trading Central reference removal confirmed',description=?,confirmation_count=2,commercial_priority=? WHERE id=?",(wording,priority_score('BROKER_TC_REFERENCE_REMOVED',90,broker.get('priority_account',False)),pending['id']))
            self.db.connection.commit(); return 0
        if not previous or not change.get('relevant'): return 0
        old=previous['current_text'] or ''
        if not any(t.lower() in old.lower() for t in self.competitor['aliases']): return 0
        return self._signal(broker,url,'POSSIBLE_REMOVAL',wording,70,old,'')

    def _signal(self,broker,url,kind,evidence,confidence,previous,current):
        now=utc_now(); title=kind.replace('_',' ').title()
        self.db.add_signal({'company_id':broker['id'],'signal_type':kind,'competitor_id':'trading_central','product_id':None,'title':title,'description':evidence,'source_url':url,'evidence_text':evidence,'detected_at':now,'confidence_score':confidence,'commercial_priority':priority_score(kind,confidence,broker.get('priority_account',False)),'previous_value':previous,'current_value':current,'ai_reasoning_summary':'Deterministic evidence-first V1 classification.','created_at':now})
        return 1
