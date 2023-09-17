import logging
import RHUtils
from eventmanager import Evt
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from plugins.MultiGP_Toolkit.multigpAPI import multigpAPI

logger = logging.getLogger(__name__)

class RHmanager():

    _multigp_cred_set = False

    def __init__(self, rhapi):
        self._rhapi = rhapi
        self.multigp = multigpAPI()

    def verify_creds(self, args):

        if self._multigp_cred_set is False:

            self.multigp.set_apiKey(self._rhapi.db.option('apiKey'))

            if self.multigp.pull_chapter():
                chapter_name = self.multigp.get_chapterName()
                message = "API key for " + chapter_name + " has been recognized"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            else:
                message = "API key cannot be verified. Please check the entered key or the RotorHazard system's internet connection"
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return
            
            #  The Session ID was supposedly replaced by the Chapter API key. Keeping fucntionality commented in case of something breaking
            #errors = self.multigp.set_sessionID(self._rhapi.db.option('mgp_username'), self._rhapi.db.option('mgp_password'))
            #if errors:
            #    for error in errors:
            #        self._rhapi.ui.message_notify(errors[error])
            #    return
            #else: 
            #    userName = self.multigp.get_userName()
            #    message = userName + " has been signed and will remain logged in until system reboot."
            #    self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            self._multigp_cred_set = True

            self.setup_plugin()
            message = "MultiGP tools can now be accessed under the Format tab."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    def setup_plugin(self):
        self._rhapi.events.on(Evt.LAPS_SAVE, self.auto_tools)
        self._rhapi.events.on(Evt.LAPS_RESAVE, self.auto_slot_score)
        self._rhapi.events.on(Evt.CLASS_ADD, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_DUPLICATE, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_ALTER, self.results_class_selector)
        self._rhapi.events.on(Evt.CLASS_DELETE, self.results_class_selector)
        self.setup_main_tools()

    def auto_tools(self, args):
        self.auto_slot_score(args)
        self.auto_zippyq(args)

    def setup_main_tools(self):
        # Panel   
        self._rhapi.ui.register_panel('multigp_tools', 'MultiGP Tools', 'format', order=0)

        # Import Tools
        self.setup_race_selector()
        self._rhapi.ui.register_quickbutton('multigp_tools', 'refresh_events', 'Refresh MultiGP Races', self.setup_race_selector)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'import_pilots', 'Import Pilots', self.import_pilots)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'import_class', 'Import Race', self.import_class)
        
        # Export Tools
        self.results_class_selector()

        auto_slot_score_text = self._rhapi.language.__('Automatically push race results')
        auto_slot_score = UIField('auto_slot_score', auto_slot_score_text, field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_slot_score, 'multigp_tools')

        auto_zippy_text = self._rhapi.language.__('Automatically pull ZippyQ rounds')
        auto_zippy = UIField('auto_zippy', auto_zippy_text, field_type = UIFieldType.CHECKBOX)
        self._rhapi.fields.register_option(auto_zippy, 'multigp_tools')

        zippyq_round_text = self._rhapi.language.__('ZippyQ round number')
        zippyq_round = UIField('zippyq_round', zippyq_round_text, field_type = UIFieldType.BASIC_INT, value = 1)
        self._rhapi.fields.register_option(zippyq_round, 'multigp_tools')

        self._rhapi.ui.register_quickbutton('multigp_tools', 'zippyq_import', 'Import ZippyQ Round', self.manual_zippyq)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_results', 'Push Class Results', self.push_results)
        self._rhapi.ui.register_quickbutton('multigp_tools', 'push_bracket', 'Push Class Rankings', self.push_bracketed_rankings)
        # The implementation for Global Qualifier results will be added for the 2024 season. Currently, there isn't a way to test functionality
        # self._rhapi.ui.register_quickbutton('multigp_tools', 'push_global', 'Push Global Qualifer Results', self.push_global_qualifer)        
        self._rhapi.ui.register_quickbutton('multigp_tools', 'finalize_results', 'Finalize Event', self.finalize_results)

    # Race selector
    def setup_race_selector(self, args = None):
        self.multigp.pull_races()
        race_list = [UIFieldSelectOption(value = None, label = "")]
        for race_label in self.multigp.get_races():
            race = UIFieldSelectOption(value = race_label, label = race_label)
            race_list.append(race)

        race_selector = UIField('race_select', 'MultiGP Race', field_type = UIFieldType.SELECT, options = race_list)
        self._rhapi.fields.register_option(race_selector, 'multigp_tools')

        self._rhapi.ui.broadcast_ui('format')

    # Import pilots and set MultiGP PilotID
    def import_pilots(self, args):
        selected_race = self._rhapi.db.option('race_select')
        if not selected_race:
            message = "Select a MultiGP Race to import pilots from"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        db_pilots = self._rhapi.db.pilots
        self.multigp.pull_race_data(selected_race)

        for mgp_pilot in self.multigp.get_pilots():
            db_match = None
            for db_pilot in db_pilots:
                    if db_pilot.callsign == mgp_pilot['userName']:
                        db_match = db_pilot
                        break

            mgp_pilot_name = mgp_pilot['firstName'] + " " + mgp_pilot['lastName']
            if db_match:
                db_pilot, _ = self._rhapi.db.pilot_alter(db_match.id, name = mgp_pilot_name)
            else:
                db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = mgp_pilot['userName'])

            self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': mgp_pilot['pilotId']})

        self._rhapi.ui.broadcast_pilots()
        message = "Pilots imported"
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Import classes from event
    def import_class(self, args):
        selected_race = self._rhapi.db.option('race_select')
        if not selected_race:
            message = "Select a MultiGP Race to import"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        self.multigp.pull_race_data(selected_race)
        schedule = self.multigp.get_schedule()

        info = """Note: Any race class with the Rounds field set to a value **less than 2** will have it's results pushed with the MultiGP round number set to the race's heat number, and the MultiGP heat set to 1. This special formating is required for ZippyQ results."""
        translated_info = self._rhapi.language.__(info)

        if self.multigp.get_disableSlotAutoPopulation() == "0":
            num_rounds = len(schedule['rounds'])
            heat_advance_type = 1

            race_class = self._rhapi.db.raceclass_add(name=selected_race, description=translated_info, rounds=num_rounds, heat_advance_type=heat_advance_type)
            db_pilots = self._rhapi.db.pilots
            slot_list = []
            for heat in schedule['rounds'][0]['heats']:
                heat_data = self._rhapi.db.heat_add(name=heat['name'], raceclass=race_class.id)
                rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)
                
                for index, entry in enumerate(heat['entries']):
                    db_match = None
                    try:
                        for db_pilot in db_pilots:
                            if db_pilot.callsign == entry['userName']:
                                db_match = db_pilot
                                break

                        if db_match:
                            slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_match.id})
                        else:
                            mgp_pilot_name = entry['firstName'] + " " + entry['lastName']
                            db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = entry['userName'])
                            self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': entry['pilotId']})
                            slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_pilot.id})
                    except:
                        continue
            
            self._rhapi.db.slots_alter_fast(slot_list)
            
        else:
            num_rounds = 1
            heat_advance_type = 0
            race_class = self._rhapi.db.raceclass_add(name=selected_race, description=translated_info, rounds=num_rounds, heat_advance_type=heat_advance_type)

        self._rhapi.ui.broadcast_raceclasses()
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_ui('format')
        message = "Race class imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Setup RH Class selector
    def results_class_selector(self, args = None):
        class_list = [UIFieldSelectOption(value = None, label = "")]
        
        for event_class in self._rhapi.db.raceclasses:
            race_class = UIFieldSelectOption(value = event_class.id, label = event_class.name)
            class_list.append(race_class)
        
        class_selector = UIField('class_select', 'RotorHazard Class', field_type = UIFieldType.SELECT, options = class_list)
        self._rhapi.fields.register_option(class_selector, 'multigp_tools')

        self._rhapi.ui.broadcast_ui('format')

    # Configure ZippyQ round
    def zippyq(self, raceclass_id, selected_race, heat_num):
        self.multigp.pull_additional_rounds(selected_race, heat_num)
        data = self.multigp.get_round()
        db_pilots = self._rhapi.db.pilots

        try:
            heat_name = data['rounds'][0]['name']
        except:
            message = "ZippyQ round doesn't exist"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        slot_list = []
        for heat in data['rounds'][0]['heats']:
            heat_data = self._rhapi.db.heat_add(name=heat_name, raceclass=raceclass_id)
            rh_slots = self._rhapi.db.slots_by_heat(heat_data.id)
            
            for index, entry in enumerate(heat['entries']):
                db_match = None
                try:
                    for db_pilot in db_pilots:
                        if db_pilot.callsign == entry['userName']:
                            db_match = db_pilot
                            break

                    if db_match:
                        slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_match.id})
                    else:
                        mgp_pilot_name = entry['firstName'] + " " + entry['lastName']
                        db_pilot = self._rhapi.db.pilot_add(name = mgp_pilot_name, callsign = entry['userName'])
                        self._rhapi.db.pilot_alter(db_pilot.id, attributes = {'multigp_id': entry['pilotId']})
                        slot_list.append({'slot_id':rh_slots[index].id, 'pilot':db_pilot.id})
                except:
                    continue
        
        self._rhapi.db.slots_alter_fast(slot_list)
        self._rhapi.ui.broadcast_pilots()
        self._rhapi.ui.broadcast_heats()
        message = "ZippyQ round imported."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Manually trigger ZippyQ round configuration
    def manual_zippyq(self, args):
        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        if not selected_race or not selected_class:
            message = "Select a MultiGP Race to import round from and a RH Class to add the round to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return
        
        self.zippyq(selected_class, selected_race, self._rhapi.db.option('zippyq_round'))

    # Automatically trigger next ZippyQ round configuration
    def auto_zippyq(self, args): 
        if self._rhapi.db.option('auto_zippy') == "1":

            message = "Automatically downloading next ZippyQ round..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            race_info = self._rhapi.db.race_by_id(args['race_id'])
            class_id = race_info.class_id
            selected_race = self._rhapi.db.raceclass_by_id(class_id).name
            next_round = race_info.heat_id + 1

            self.zippyq(class_id, selected_race, next_round)

    # Slot and Score
    def slot_score(self, race_info, selected_race):
        num_rounds = self._rhapi.db.raceclass_by_id(race_info.class_id).rounds
        results = self._rhapi.db.race_results(race_info.id)["by_race_time"]
        for result in results:
            slot = result["node"] + 1
            pilotID = self._rhapi.db.pilot_attribute_value(result["pilot_id"], 'multigp_id')
            pilot_score = result["points"]
            totalLaps = result["laps"]
            totalTime = result["total_time_raw"] * .001
            fastestLapTime = result["fastest_lap_raw"] * .001
            fastestConsecutiveLapsTime = result["consecutives_raw"] * .001
            consecutives_base = result["consecutives_base"]

            if num_rounds < 2:
                round = race_info.heat_id
                heat = 1
            else:
                round = race_info.round_id
                heat = race_info.heat_id
                
            if not self.multigp.push_slot_and_score(selected_race, round, heat, slot, pilotID, 
                    pilot_score, totalLaps, totalTime, fastestLapTime, fastestConsecutiveLapsTime, consecutives_base):
                message = "Results push to MultiGP FAILED. Check the timer's internet connection."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))
                return False
            
        return True

    # Automatially push results of heat
    def auto_slot_score(self, args):

        if self._rhapi.db.option('auto_slot_score') == "1":

            message = "Automatically uploading results..."
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

            race_info = self._rhapi.db.race_by_id(args['race_id'])
            class_id = race_info.class_id
            selected_race = self._rhapi.db.raceclass_by_id(class_id).name
            
            if self.slot_score(race_info, selected_race):
                message = "Results successfully pushed to MultiGP."
                self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class results
    def push_results(self, args):
        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        if not selected_race or not selected_class:
            message = "Select a RH Class to pull results from and a MultiGP Race to send results to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        races = self._rhapi.db.races_by_raceclass(selected_class)
        for race_info in races:
            if not self.slot_score(race_info, selected_race):
                return

        message = "Results successfully pushed to MultiGP."
        self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Push class ranking
    def push_bracketed_rankings(self, args):
        selected_race = self._rhapi.db.option('race_select')
        selected_class = self._rhapi.db.option('class_select')
        if not selected_race or not selected_class:
            message = "Select a RH Class to pull rankings from and a MultiGP Race to send rankings to"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        results_class = self._rhapi.db.raceclass_ranking(selected_class)
        results = []
        for pilot in results_class["ranking"]:
            multigp_id = int(self._rhapi.db.pilot_attribute_value(pilot['pilot_id'], 'multigp_id'))
            class_position = (pilot['position'])
            result_dict = {"orderNumber" : class_position, "pilotId" : multigp_id}
            results.append(result_dict)

        push_status = self.multigp.push_overall_race_results(selected_race, results)
        if push_status:
            message = "Rankings pushed to MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        else:
            message = "Failed to push rankings to MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))

    # Coming in the 2024 season
    #def push_global_qualifer(self, args):
    #    pass

    # Finalize race results
    def finalize_results(self, args):
        selected_race = self._rhapi.db.option('race_select')
        if not selected_race:
            message = "Select a MultiGP Race to finalize"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
            return

        push_status = self.multigp.finalize_results(selected_race)
        if push_status:
            message = "Results finalized on MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
        else:
            message = "Failed to finalize results on MultiGP"
            self._rhapi.ui.message_notify(self._rhapi.language.__(message))
