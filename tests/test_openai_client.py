import json
import sys
import types

from src.openai_client import (
    ClaimExtraction,
    extract_claim_with_openai,
    generate_text_with_openai,
)


class FakeCompletions:

    def create(
        self,
        **kwargs,
    ):

        assert (
            kwargs["model"]
            ==
            "openai/gpt-oss-20b"
        )


        # Structured extraction request
        if (
            "response_format"
            in kwargs
        ):

            response_format = (
                kwargs[
                    "response_format"
                ]
            )


            assert (
                response_format[
                    "type"
                ]
                ==
                "json_schema"
            )


            assert (
                response_format[
                    "json_schema"
                ][
                    "strict"
                ]
                is True
            )


            schema = (
                response_format[
                    "json_schema"
                ][
                    "schema"
                ]
            )


            assert (
                schema[
                    "additionalProperties"
                ]
                is False
            )


            assert set(
                schema[
                    "required"
                ]
            ) == {

                "name",
                "claim_amount",
                "policy_number",
                "all_policy_numbers",
                "conflicts",
                "confidence",

            }


            payload = {

                "name":
                    "Jane Doe",

                "claim_amount":
                    4250.0,

                "policy_number":
                    "POL-1001",

                "all_policy_numbers":
                    [
                        "POL-1001"
                    ],

                "conflicts":
                    [],

                "confidence":
                    0.99,
            }


            return (
                types.SimpleNamespace(

                    choices=[

                        types.SimpleNamespace(

                            message=
                                types.SimpleNamespace(

                                    content=
                                        json.dumps(
                                            payload
                                        )
                                )
                        )
                    ]
                )
            )


        # Letter-generation request

        return (
            types.SimpleNamespace(

                choices=[

                    types.SimpleNamespace(

                        message=
                            types.SimpleNamespace(

                                content=
                                    "Draft letter"
                            )
                    )
                ]
            )
        )


class FakeChat:

    def __init__(
        self,
    ):

        self.completions = (
            FakeCompletions()
        )


class FakeOpenAI:

    def __init__(
        self,
        **kwargs,
    ):

        assert (
            kwargs[
                "api_key"
            ]
            ==
            "test-groq-key-not-real"
        )


        assert (
            kwargs[
                "base_url"
            ]
            ==
            "https://api.groq.com/openai/v1"
        )


        assert (
            kwargs[
                "timeout"
            ]
            ==
            30.0
        )


        assert (
            kwargs[
                "max_retries"
            ]
            ==
            2
        )


        self.chat = (
            FakeChat()
        )


def install_fake_openai(
    monkeypatch,
):

    module = types.ModuleType(
        "openai"
    )


    module.OpenAI = (
        FakeOpenAI
    )


    monkeypatch.setitem(
        sys.modules,
        "openai",
        module,
    )


    monkeypatch.setenv(
        "GROQ_API_KEY",
        "test-groq-key-not-real",
    )


    monkeypatch.setenv(
        "GROQ_MODEL",
        "openai/gpt-oss-20b",
    )


def test_structured_extraction_wiring(
    monkeypatch,
):

    install_fake_openai(
        monkeypatch
    )


    result = (
        extract_claim_with_openai(

            "Claimant Name: Jane Doe"

        )
    )


    assert (
        result[
            "name"
        ]
        ==
        "Jane Doe"
    )


    assert (
        result[
            "policy_number"
        ]
        ==
        "POL-1001"
    )


def test_letter_generation_wiring(
    monkeypatch,
):

    install_fake_openai(
        monkeypatch
    )


    assert (

        generate_text_with_openai(
            "system",
            "user",
        )

        ==

        "Draft letter"
    )