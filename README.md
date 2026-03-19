# tts_starter_template
A starter repository to help users quickly set up a Teamtools Studio project with common structure, configs, and package scaffolding. 

![Project logo](https://github.com/NASA-JPL-Teamtools-Studio/teamtools_documentation/blob/main/docs/images/teamtools_studio_wide.png)

## About Teamtools Studio

Teamtools Studio Utilities is part of JPL's Teamtools Studio (TTS).

TTS is an effort originated in JPL's Planning and Execution section to centralize shared repositories across missions. This benefits JPL by reducing cost through reducing duplicated code, collaborating across missions, and unifying standards for development and design across JPL.

Although Planning and Execution is primarily concerned with flight operations, the TTS suite has been generalized and atomized to the point where many of these tools are applicable during other mission phases and even in non-spaceflight contexts. Through our work flying space missions, we hope to provide tools to the open source community that have utility in data analysis or planning for any complex system where failure is not an option.

For more infomation on how to contribute, and how these libraries form a complete ecosystem for high reliability data analysis, see the [Full TTS Documentation](https://nasa-jpl-teamtools-studio.github.io//teamtools_documentation/).

## What is Teamtools Starter Template?

### Overview

This is a simple starter kit for new repositories to help enforce consistent style and packaging conventions common to all TTS libraries.
It is important to follow these conventions as much of our CI/CD is built around assumptions about how these libraries are built.

* Notice that we use pyproject.toml with a simple helper setup.py to bootstrap older Python versions
* Notice that we deploy tests within src/library. This is so we can call them via pytest --pyargs [mylib]

## Making Your Own Repository From This Template

This is a "template" GitHub repository, which makes it much simpler to copy without needing to for example manage a fork.

If you are a member of this GitHub organization, this repository should show up under the templates avaliable to you
when creating a new repository normally.


