from __future__ import absolute_import
from engage_app import app
from datetime import datetime
from celery_once import QueueOnce
from engage_scraper.scraper_logics.santamonica_scraper_models import Committee, Agenda, AgendaItem
from engage_scraper.scraper_utils import dbutils
from engage_scraper.scraper_logics.santamonica_scraper_logic import SantaMonicaScraper
from .process_agenda_to_pdf import write_pdf_for_agenda
import logging

logging.basicConfig()
log = logging.getLogger(__name__)

engine = dbutils.create_postgres_connection()
Session = dbutils.create_postgres_session(engine)


@app.task(base=QueueOnce, once={'graceful': True})
def scrape_councils():
    # Make sure you have set the POSTGRES_URI and POSTGRES_DB env variables
    session = Session()
    i = 0
    for committee in session.query(Committee):
        i += 1
        scraper = SantaMonicaScraper(committee=committee.name)
        scraper.get_available_agendas()
        scraper.scrape()
        log.error("Done scraping {} at {}".format(
            committee.name, datetime.now()))
    if i == 0:
        log.error("FIRST TIME")
        session.add(Committee(name="Santa Monica City Council",
                              email="engage@engage.town",
                              cutoff_offset_days=0,
                              cutoff_hour=12,
                              cutoff_minute=0
                              ))
        session.commit()
        for committee in session.query(Committee):
            scraper = SantaMonicaScraper(committee=committee.name)
            scraper.get_available_agendas()
            scraper.scrape()
            log.error("Done scraping {} at {}".format(
                committee.name, datetime.now()))


@app.task(base=QueueOnce, once={'graceful': True})
def process_agenda_to_pdf():
    session = Session()
    dt = int(datetime.now().timestamp())
    for agenda in session.query(Agenda):
        try:
            if not agenda.processed and dt >= agenda.pdf_time:
                # process the agenda
                committee = session.query(Committee).filter(
                    Committee.id == agenda.committee_id).first()
                agenda_items = session.query(AgendaItem).filter(
                    AgendaItem.agenda_id == agenda.id).order_by(AgendaItem.agenda_item_id).all()
                if len(agenda_items) > 0:
                    write_pdf_for_agenda(
                        committee, agenda, agenda_items, session)
                log.error("Done processing {}".format(agenda.id))
        except:
            log.error("Error in PDF generation at time: {} for agenda id: {}".format(
                str(dt), agenda.id))
    session.commit()
    session.close()
