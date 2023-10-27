#!/usr/bin/env python3
from __future__ import annotations

import os

try:
    import httpx
except ImportError:
    raise ImportError("Please install httpx with 'pip install httpx' ")

from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.widgets import Input, Markdown, Footer, DataTable, Header, OptionList, Label, LoadingIndicator
from textual.binding import Binding

CONGRESS_LIST = """114
115
116
117
118""".splitlines()


class CongressTui(App):
    """Browses congress.gov API"""

    # key bindings displayed in footer
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
    ]
    # app css
    CSS_PATH = "congress-tui.tcss"

    # current state props
    current_content_type = "bill"
    current_congress = "118"
    current_bill_type = None
    current_bill_num = None

    # get api key from env var, else use demo key
    GOV_API_KEY = os.getenv('GOV_API_KEY')
    if GOV_API_KEY is None:
        GOV_API_KEY = "DEMO_KEY"

    def compose(self) -> ComposeResult:

        yield Header()

        # ROW-1: select lists
        with Vertical():
            yield Label(f"Congress: {self.current_congress}",
                        classes='header',
                        id='congress-label')
            yield OptionList(
                "114",
                "115",
                "116",
                "117",
                "118",
                id="congress-list"
            )

        with Vertical():
            yield Label(f"Bill Type: {self.current_bill_type}",
                        classes='header',
                        id='bill-type-label')
            yield OptionList(
                "hr", "s", "sjres", "hjres", "hconres", "sconres", "hres", "sres",
                id="type-list"
            )

        with Vertical():
            yield Label(f"Bill Number: {self.current_bill_num}",
                        classes='header',
                        id='bill-num-label')
            yield OptionList(id="bill-num-list")

        # ROW-2 loadings
        yield LoadingIndicator(id="status-progress")

        # ROW-3: results markdown
        with VerticalScroll(id="results-container"):
            yield Markdown(id="results")
            yield DataTable(id="table")

        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "congress-tui"
        self.sub_title = "browse bills"

        # default to the most recent congress and do search
        self.query_one("#congress-list", OptionList).action_last()
        self.query_one("#congress-list", OptionList).action_select()

    async def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:

        if message.option_list.id == 'congress-list':
            self.current_congress = message.option.prompt
            self.current_bill_type = None
            self.current_bill_num = None
            self.clear_bill_num()
            self.query_one("#congress-label", Label).update(f"Congress: {self.current_congress}")
            self.query_one("#bill-type-label", Label).update(f"Bill Type: {self.current_bill_type}")
            self.query_one("#bill-num-label", Label).update(f"Bill Number: {self.current_bill_num}")
        if message.option_list.id == 'type-list':
            self.current_bill_type = message.option.prompt
            self.current_bill_num = None
            self.clear_bill_num()
            self.query_one("#bill-type-label", Label).update(f"Bill Type: {self.current_bill_type}")
            self.query_one("#bill-num-label", Label).update(f"Bill Number: {self.current_bill_num}")
        if message.option_list.id == 'bill-num-list':
            self.current_bill_num = message.option.prompt
            self.query_one("#bill-num-label", Label).update(f"Bill Number: {self.current_bill_num}")
        self.make_api_call()

    def clear_bill_num(self) -> None:
        num_list = self.query_one('#bill-num-list', OptionList)
        num_list.clear_options()
        self.current_bill_num = None

    async def on_input_changed(self, message: Input.Changed) -> None:
        self.console.print("INPUT CHANGED")

        """A coroutine to handle a text changed message."""
        if message.input.id == 'bill-num':
            if message.value:
                self.current_bill_num = message.value
                self.make_api_call()
            else:
                # Clear the results
                await self.query_one("#results", Markdown).update("")

    @work(exclusive=True)
    async def make_api_call(self) -> None:

        # show progress
        self.query_one("#status-progress", LoadingIndicator).visible = True

        url = f"https://api.congress.gov/v3/{self.current_content_type}"

        # BILL
        if self.current_content_type == "bill":
            # construct url
            url += f"/{self.current_congress}"
            if self.current_bill_type is not None:
                url += f"/{self.current_bill_type}"
                if self.current_bill_num is not None:
                    url += f"/{self.current_bill_num}"
            url += f"?format=json&api_key={self.GOV_API_KEY}"
            # make http call
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.get(url)
                try:
                    results = response.json()
                except httpx.HTTPError as exc:
                    print(f"Error while requesting {exc.request.url!r}.")
            # update view
            markdown = self.make_bill_markdown(results)
            await self.query_one("#results", Markdown).update(markdown)

            # hide progress
            self.query_one("#status-progress", LoadingIndicator).visible = False

    def load_results_table(self, results: any):
        if isinstance(results['bills'], list):
            for result in results['bills']:
                table = self.query_one(DataTable)
                table.add_row(result['number'], result['title'])

    def make_bill_markdown(self, results: any) -> str:
        """Convert the results in to markdown."""
        lines = []
        # single bill
        if results.get('bill') is not None:
            lines.append(f"{results['bill']['congress']} Congress -> "
                         f"{results['bill']['type']} {results['bill']['number']}")
            lines.append("")
            lines.append(f"# {results['bill']['number']} - {results['bill']['title']}")

            # chamber
            if results.get('bill').get('originChamber') is not None:
                lines.append("")
                lines.append(f"*Chamber*: {results['bill']['originChamber']}")

            # policy area
            if results.get('bill').get('policyArea') is not None:
                lines.append("")
                lines.append(f"*Policy Area*: {results['bill']['policyArea']['name']}")

            # introduced
            if results.get('bill').get('introducedDate') is not None:
                lines.append("")
                lines.append(f"*Introduced*: {results['bill']['introducedDate']}")

            # latest action
            if results.get('bill').get('latestAction') is not None:
                lines.append("")
                lines.append(f"*Latest Action*: {results['bill']['latestAction']['actionDate']} - "
                             f"{results['bill']['latestAction']['text']}")
            # cost estimates
            if results.get('bill').get('cboCostEstimates') is not None:
                lines.append("")
                lines.append("*Cost Estimates*:")
                for estimate in results['bill']['cboCostEstimates']:
                    lines.append(f"- {estimate['title']}")
            # sponsors
            if results.get('bill').get('sponsors') is not None:
                lines.append("")
                lines.append(f"*Sponsors*:")
                for sponsor in results['bill']['sponsors']:
                    lines.append(f"- {sponsor['fullName']}")

            # cosponsors
            if results.get('bill').get('cosponsors') is not None:
                lines.append("")
                lines.append(f"*Coponsors*: {results['bill']['cosponsors']['count']}")

            # laws
            if results.get('bill').get('laws') is not None:
                lines.append("")
                lines.append(f"*Laws*:")
                for law in results['bill']['laws']:
                    lines.append(f"- {law['number']} - {law['type']}")

            # text versions
            if results.get('bill').get('textVersions') is not None:
                lines.append("")
                lines.append(f"*Text Versions*: {results['bill']['textVersions']['count']}")

            # summaries
            if results.get('bill').get('summaries') is not None:
                lines.append("")
                lines.append(f"*Summaries*: {results['bill']['summaries']['count']}")

            # subjects
            if results.get('bill').get('subjects') is not None:
                lines.append("")
                lines.append(f"*Subjects*: {results['bill']['subjects']['count']}")

            # constitutionalAuthorityStatementText
            if results.get('bill').get('constitutionalAuthorityStatementText') is not None:
                lines.append("")
                lines.append(f"*Constitutional Authority Statement*: "
                             f"{results['bill']['constitutionalAuthorityStatementText']}")

            # related bills
            if results.get('bill').get('relatedBills') is not None:
                lines.append("")
                lines.append(f"*Related Bills*: {results['bill']['relatedBills']['count']}")

        # list of bills
        if results.get('bills') is not None:
            num_list = self.query_one('#bill-num-list', OptionList)
            num_list.clear_options()

            if isinstance(results['bills'], list):
                for result in results['bills']:
                    if self.current_bill_type is not None:
                        num_list.add_option(result['number'])
                    lines.append(f"# {result['number']} - {result['title']}")
                    lines.append("")
                    lines.append(f"**Congress**: {result['congress']}")
                    lines.append("")
                    lines.append(f"**Type**: {result['type']}")
                    lines.append("")
                    lines.append(f"**Chamber**: {result['originChamber']}")
                    lines.append("")
                    lines.append(f"**Updated**: {result['updateDate']}")
                    lines.append("")
                    lines.append(
                        f"**Lastest Action**: {result['latestAction']['text']} ({result['latestAction']['actionDate']})")
                    lines.append("")
                    lines.append(f"**Link**: {result['url']}")

        return "\n".join(lines)


def main():
    print("Warming up...")
    print(CongressTui().run())


if __name__ == "__main__":
    main()
