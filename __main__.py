import asyncio
from textual.app import App
from textual.widgets import Header, Footer, Input, Button, TextArea, LoadingIndicator
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from nats.aio.client import Client as NATS

class NATSApp(App):
    CSS = """
    #message_area {
        height: 1fr;
        border: solid white;
        padding: 1;
    }
    #loading {
        width: 100%;
        height: 3;
        content-align: center middle;
        display: none;  /* Nasconde completamente l'indicatore quando non visibile */
    }
    #loading.visible {
        display: block;  /* Mostra l'indicatore quando è visibile */
    }
    """

    nats_client = NATS()
    server = reactive("")
    current_subject = reactive("")
    current_sid = None  # Oggetto Subscription per la sottoscrizione corrente
    is_connected = reactive(False)  # Stato della connessione
    is_connecting = reactive(False)  # Stato della connessione in corso

    async def on_mount(self) -> None:
        # Titolo dell'applicazione
        self.title = "NATS Messenger"

        # Creazione dell'interfaccia
        self.server_input = Input(placeholder="Inserisci il server NATS (es. nats://localhost:4222)", id="server_input")
        self.subject_input = Input(placeholder="Inserisci il subject di ascolto", id="subject_input")
        self.message_area = TextArea(id="message_area", read_only=True)  # Usiamo TextArea per i messaggi
        self.message_input = Input(placeholder="Scrivi un messaggio da inviare", id="message_input")
        self.connect_button = Button("Connetti", id="connect_button")
        self.send_button = Button("Invia", id="send_button")
        self.loading_indicator = LoadingIndicator(id="loading")  # Indicatore di caricamento
        self.loading_indicator.visible = False  # Inizialmente nascosto

        # Layout
        await self.mount(
            Header(),
            Footer(),
            Container(
                self.server_input,
                self.subject_input,
                self.loading_indicator,
                self.connect_button,
                VerticalScroll(self.message_area),
                self.message_input,
                self.send_button,
            ),
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect_button":
            if not self.is_connected:
                await self.connect_to_nats()
            else:
                await self.update_subscription()  # Cambia il subject
        elif event.button.id == "send_button":
            await self.send_message()

    async def connect_to_nats(self) -> None:
        self.server = self.server_input.value

        if not self.server:
            self.message_area.text += "Inserisci un server NATS valido.\n"
            return

        # Mostra l'indicatore di caricamento e nasconde il pulsante
        self.is_connecting = True
        self.connect_button.visible = False
        self.loading_indicator.visible = True
        self.loading_indicator.add_class("visible")  # Mostra l'indicatore

        try:
            # Timeout di connessione (5 secondi)
            await asyncio.wait_for(self.nats_client.connect(servers=[self.server]), timeout=5.0)
            self.is_connected = True
            self.connect_button.label = "Change Subject"  # Cambia l'etichetta del pulsante
            self.message_area.text += f"Connesso al server NATS: {self.server}\n"
            await self.update_subscription()  # Sottoscrive al subject iniziale
        except asyncio.TimeoutError:
            self.message_area.text += "Timeout: impossibile connettersi al server NATS.\n"
        except Exception as e:
            self.message_area.text += f"Errore di connessione: {e}\n"
        finally:
            # Nasconde l'indicatore di caricamento e mostra il pulsante
            self.is_connecting = False
            self.loading_indicator.visible = False
            self.loading_indicator.remove_class("visible")  # Nasconde l'indicatore
            self.connect_button.visible = True

    async def update_subscription(self) -> None:
        """Aggiorna la sottoscrizione al subject corrente."""
        new_subject = self.subject_input.value

        if not new_subject:
            self.message_area.text += "Inserisci un subject valido.\n"
            return

        # Annulla la sottoscrizione precedente (se esiste)
        if self.current_sid is not None:
            await self.current_sid.unsubscribe()
            self.message_area.text += f"Disiscritto dal subject: {self.current_subject}\n"

        # Sottoscrive al nuovo subject
        self.current_subject = new_subject
        self.current_sid = await self.nats_client.subscribe(self.current_subject, cb=self.handle_message)
        self.message_area.text += f"In ascolto sul subject: {self.current_subject}\n"

    async def handle_message(self, msg) -> None:
        """Callback per gestire i messaggi ricevuti."""
        self.message_area.text += f"Ricevuto: {msg.data.decode()}\n"

    async def send_message(self) -> None:
        if not self.nats_client.is_connected:
            self.message_area.text += "Non sei connesso a un server NATS.\n"
            return

        message = self.message_input.value
        if not message:
            self.message_area.text += "Inserisci un messaggio da inviare.\n"
            return

        try:
            await self.nats_client.publish(self.current_subject, message.encode())
            self.message_area.text += f"Inviato: {message}\n"
            self.message_input.value = ""  # Pulisce la casella di testo
        except Exception as e:
            self.message_area.text += f"Errore durante l'invio: {e}\n"

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Gestisce l'invio del subject."""
        if event.input.id == "subject_input":
            await self.update_subscription()

    async def on_unmount(self) -> None:
        """Chiude la connessione NATS quando l'app viene chiusa."""
        if self.nats_client.is_connected:
            await self.nats_client.close()

if __name__ == "__main__":
    app = NATSApp()
    app.run()