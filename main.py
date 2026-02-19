import queue
import weakref
import re

from niceegui import ui
import llm_server as llms

from helper import LocalFilePicker


class LlmServerWidget:

    def __init__(self) -> None:

        self.server: llms.Server = None
        self.network: Network = None
        self.model_table: ModelTable = None

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.log_area: ui.textarea = None
        self.log_timer: ui.timer = None
        self.log_button: ui.button = None

        with ui.card().classes('w-[40rem]'):
            ui.label(text='LLM Server').classes('text-lg font-medium w-full text-center')

            ui.separator()

            self.network = Network(parent=self)
            self.server = llms.Server()
            self.server.set_host(ip_address=self.network.ip_address.value, port=int(self.network.port.value))

            ui.separator()

            with ui.tabs().classes('w-full') as self.tabs:
                tab_selection = ui.tab('Selection')
                tab_loading = ui.tab('Loading')

            with ui.tab_panels(self.tabs, value=tab_selection).classes('w-full'):
                with ui.tab_panel(tab_selection):
                    self.model_table = ModelTable(parent=self)
                with ui.tab_panel(tab_loading):
                    self.model_loading = ModelLoading(parent=self)

            self.log_area = ui.textarea(
                label='Log',
                placeholder='Logs will appear here...',
                value=''
                ).props('readonly').classes('w-full').style('height: 220px; overflow:auto;')

            self.log_button = ui.button(
                text='Clear Log',
                on_click=self.clear_log,
            ).props('push color=primary')

        self.log_timer = ui.timer(
            interval=0.2,
            callback=self.flush_logs,
            active=True)

    def flush_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self.log_area.value = (self.log_area.value + line + '\n').lstrip()

        return


    def clear_log(self) -> None:
        self.log_area.value = ''
        return


class Network:
    def __init__(self, parent: 'LlmServerWidget') -> None:
        self.parent = weakref.proxy(parent)

        self.endpoint: Endpoint = None
        self.previous_states: PreviousStates = PreviousStates()

        self.by_id: dict = {}

        self.on_off: ui.button = None
        self.ip_address: ui.input = None
        self.port: ui.input = None

        ui.label(text='Endpoint').classes('text-md font-meeium')
        with ui.row().classes('items-center gap-4'):
            self.on_off = ui.button(
                text='OFF',
                on_click=self.on_toggle
                ).props('push color=grey outline')

            with ui.columns().classes('gap-1'):
                self.ip_address = ui.input(
                    label='IP Address',
                    placeholder='127.0.0.1',  # NOTE: Value supercededs placeholder.
                    value='127.0.0.1'
                    ).props('dense outlined clearable').classes('w-[10rem]')
                self.ip_address.on('change', lambda e: self.on_ip_change(e))
                self.by_id[self.ip_address.id] = self.ip_address

            ui.label(':').classes('pt-2 text-lg')

            with ui.column().classes('gap-1'):
                self.port = ui.input(
                    label='Port',
                    placeholder='8000',
                    value=8000
                    ).props('dense outlined clearable type=number').classes('w-[8rem]')
                self.port.on('change', lambda e: self.on_port_change(e))
                self.by_id[self.port.id] = self.port

            self.previous_states.endpoint = Endpoint(ip_address=self.ip_address.value, port=int(self.port.value))

    def on_toggle(self) -> None:
        if self.parent.server.is_online:
            self.parent.server.stop()
            self.on_off.text = 'OFF'
            self.on_off.props('push color=red outline')
        else:
            self.parent.server.start()
            if self.parent.server.is_online:
                self.on_off.text = 'ON'
                self.on_off.props('push color=green')
            else:
                self.parent.log_queue.put('Server failed to start.')

        return


    def on_port_change(self, e) -> None:
        MAX_PORT = 65535

        check_is_valid_port = lambda port: 1 <= port <= MAX_PORT

        port = str(self.port.value).strip()
        try:
            port = int(self.port.value)
            is_valid_port = check_is_valid_port(port)
        except Exception:
            is_valid_port = False

        if port == self.parent.server.endpoint.port:
            return

        if not is_valid_port:
            self.port.value = str(self.parent.server.endpoint.port)
            self.parent.loq_queue.put(f'Invalid port. Must be integer 1-{MAX_PORT}.')
            return

        if self.by_id[e.sender.id] == self.port:
            self.parent.server.set_host(ip_address=self.parent.server.endpoint.ip_address, port=port)
            self.parent.log_queue.put(f'Port set to {port}.')

        return


    def on_ip_change(self, e) -> None:

        check_is_valid_ip_address = lambda ip_address: bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address))

        ip_address = str(self.ip_address.value).strip()
        is_valid_ip_address = check_is_valid_ip_address(ip_address)

        if not is_valid_ip_address:
            self.parent.log_queue.put(f'IP address set to {ip_address}.')

        if self.by_id[e.sender.id] == self.ip_address:
            self.parent.server.set_host(ip_address=ip_address, port=self.parent.server.endpoint.port)
            self.parent.loq_queue.put(f'IP Address set to {ip_address}.')

        return


class ModelTable:

    def __init__(self, parent: 'LlmServerWidget') -> None:
        self.parent = weakref.proxy(parent)
        
        self.table: ui.table = None

        self.new_tag_input: str = None
        self.new_name_input: str = None

        self.by_id: dict = {}

        self._selected_models: list = []

        ui.label(text='Models').classes('text-md font-medium')
        with ui.row()classes('items-center gap-4'):
            self.table = ui.table(
                columns=[
                    {'name': 'tag', 'label': 'Tag', 'field': 'tag', 'align': 'left'},
                    {'name': 'model', 'label': 'Model', 'field': 'model', 'align': 'left'}],
                rows=[],
                row_key='key',
                ).props('selection="multiple"').classes('w-full').style('max-height: 220px; overflow:auto;')
            self.table.on('selection', self.on_table_selection)

        with ui.row().classes('items-center gap-3 mt-2'):
            with ui.column().classes('gap-1'):
                self.new_tag_input = ui.input(
                    label='Tag',
                    placeholder='Phi-4',
                    value=''
                    ).props('dense outlined clearable').classes('w-[8rem]')
                self.new_tag_input.on('change', lambda e: self.on_tag_change(e))
                self.by_id[self.new_tag_input.id] = self.new_tag_input

            ui.label(':').classes('pt-2 text-lg')

            with ui.column().classes('gap-1'):
                self.new_name_input = ui.input(
                    label='Name',
                    placeholder='microsoft/Phi-4-multimodal-instruct',
                    value=''
                    ).props('dense outlined clearable').classes('w-[20rem]')
                self.new_name_input.on('change', lambda e: self.on_name_change(e))
                self.by_id[self.new_name_input.id] = self.new_name_input

            ui.button(text='+ Add', on_click=self.on_add_model).props('push color=secondary')
            ui.button(text='Remove Selected', on_click=self.on_remove_selected).props('push color=negative outline')


    def _rows_from_table(self) -> list[dict]:
        model_list = self.parent.server.backend.models
        current_models = [{'key': i, 'tag': k, 'model': model_list[k].name} for i, k in enumerate(model_list)]

        return current_models


    def _refresh_table(self) -> None:
        self.table.rows = self._rows_from_table()
        self.table.update()
        return


    def on_tag_change(self, e) -> None:
        if not isinstance(self.new_tag_input.value, str):
            self.parent.loq_queue.put(f'Invalid model tag. Must be string.')
            self.new_tag_input = ''

        return


    def on_name_change(self, e) -> None:
        if not isinstance(self.new_name_input.value, str):
            self.parent.loq_queue.put(f'Invalid model name. Must be string.')
            self.new_name_input = ''

        return


    def on_add_model(self) -> None:
        tag = str(self.new_tag_input.value).strip()
        name = str(self.new_name_input.value).strip()
        if not tag or not name:
            self.parent.log_queue.put('Both "Tag" and "Name" fields are required to add a model.')
            return

        if tag in self.parent.server.backend.models:
            self.parent.log_queue.put(f'A model by tag "{tag}" already exists.')
            return

        self.parent.server.add_model(tag=tag, name=name)

        self._refresh_table()

        self.new_tag_input.value = ''
        self.new_name_input.value = ''

        self.parent.model_loading.model_select.options = list(self.parent.server.backend.models.keys())
        self.parent.model_loading.model_select.update()

        self.parent.loq_queue.put(f'Added model, {tag}: {name}')

        return


    def on_table_selection(self, e) -> None:
        currently_selected = self._selected_models

        selected = getattr(e, 'args', [])
        changed_items = [item['tag'] for item in selected['rows']]

        if selected['added']:
            self._selected_models.extend([tag for tag in changed_items if tag not in currently_selected])
        else:
            self._selected_models = [i for i in currently_selected if i not in changed_items]

        return


    def on_remove_selected(self) -> None:

        if not self._selected_models:
            self.parent.log_queue.put('No connections selected to remove.')
            return

        for tag in self._selected_models:
            self.parent.server.del_model(tag=tag)

        self._refresh_table()
        self._selected_models.clear()

        self.parent.model_loading.model_select.options = list(self.parent.server.backend.models.keys())
        self.parent.model_loading.model_select.update()

        self.parent.loq_queue.put(f'Removed model: {tag}')

        return


class ModelLoading:

    def __init__(self, parent: 'LlmServerWidget') -> None:

        self.parent = weakref.proxy(parent)

        self.by_id: dict = {}

        self.model_select: ui.select = None
        self.location: ui.input = None
        self.button_browse: ui.button = None
        self.button_load: ui.button = None

        with ui.row().classes('items-start gap-3'):
            ui.label('Select:').classes('pt-2 font-medium')

            self.model_select = ui.select(
                options=list(self.parent.server.backend.models.keys()),
                label='Model',
                on_change=self.on_model_select
                ).props('outlined dense').classes('w-[8rem]')

        with ui.row().classes('items-start gap-3'):

            ui.label('Location:').classes('pt-2 font-medium')

            self.location = ui.input(
                label='Model cache',
                placeholder='.../model cache',
                value='',
                ).props('dense outlined clearable').classes('w-[20rem]')
            self.location.on('change', lambda e: self.on_location_change(e))

            self.button_browse = ui.button(
                text='Browse',
                on_click=self.on_browse).props('unelevated')

        with ui.row().classes('w-full gap-1 justify-center'):
            self.button_load = ui.button(
                text='Load',
                color='gold',
                on_click=self.on_load).props('unelevated')


    def on_model_select(self, e):
        self.selected_model = e.value
        self.location.value = ''
        return

    def on_location_change(self, e):
        self.location.value = e.value
        return

    def on_load(self, e):
        self.parent.server.load_model(tag=self.selected_model, location=self.location.value)
        self.parent.log_queue.put(f'Model "{self.selected_model}" loaded.')
        self.location.value = ''

    async def on_browse(self) -> None:
        import os
        start_dir = os.path.expanduser('~')
        file_path = await LocalFilePicker(start_dir, multiple=False)

        if not file_path:
            return

        self.location.value = file_path[0]
        self.location.update()

        return
            
with ui.row().classes('w-full justify-center p-6'):
    LlmServerWidget()

ui.run(title='LLM Server Widget', port=8000)
