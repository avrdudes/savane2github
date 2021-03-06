# Savane to GitHub Migration Tool

The purpose of this tool is to migrate a Savane project hosted on Savannah to GitHub.
This tool is capable of migrating bugs, tasks, and patches and creating the respective issues on GitHub.

## Prerequisites

This tool requires Python 3.8 and the packages 'PyGithub' and 'Beautiful Soup'.

For instance, under Linux/Ubuntu, you would run

```console
sudo apt install python3 python3-pip
pip install --upgrade PyGithub beautifulsoup4
```

## Usage

Using the tool requires multiple steps, which gives you the opportunity to inspect the result after each step,
before you export the issues to GitHub.

The basic procedure is as follows:

- List items of a Savane project
  - In this step, a list of bugs, tasks, or patches will be created using the 'Browse' feature of the projects website.
  - The result will be written to a JSON list file, containing the IDs and a description.
- Download HTML pages from a Savane project
  - In this step, all HTML tracker pages will be downloaded.
  - The HTML pages to be downloaded are specified by the JSON list file.
- Import HTML pages
  - In this step, the downloaded HTML pages will be parsed.
  - The HTML pages to be parsed are specified by the JSON list file. 
  - The result will be written to a JSON tracker file, containing a combined list of bugs, tasks, or patches.
- Export items to GitHub
  - In this final step, the JSON tracker file will be exported to GitHub.
  - For each item in the JSON tracker file, a GitHub issue will be created. One or more comments may be created for every issue.

Note: This script assumes that you successfully authenticated yourself as a Savannah member using the --username and --password option.

## Example

```console
./savane2github.py --project avrdude --username <myuser> --password <mypw> --list-bugs
./savane2github.py --project avrdude --username <myuser> --password <mypw> --download-bugs
./savane2github.py --project avrdude --import-bugs
./savane2github.py --project avrdude --dump-bugs
./savane2github.py --project avrdude --access-token <mytoken> --export-bugs
```

## SourceForge.net migration

With the help of the companion script `import_sf.py`, it is also
possible to migrate issue trackers from SourceForge.net projects.

In order to do this, go to the SourceForge project Admin tab, and then
pick "Export". Select all the trackers you'd like to export.
Attachments are not migrated by the scripts, so you can leave them out
unless you'd like to have them in the exported archive anyway.

Unpack the archive locally then. The trackers are recorded in JSON
files like `bugs.json` etc.

Run `import_sf.py` on each of these files, redirect the output into
a project subdirectory into a new JSON file that with the name
`trackers_`_name-of-tracker_`s.json`.

This file is the equivalent of the third step above. You can thus
use `savane2github.py` on it with the `--export-`_name-of-tracker_
and `--dump-`_name-of-tracker_ options. In addition to bugs and
patches, feature requests can also be handled at that point.


## Issues

- This script was written to migrate the 'avrdude' Savannah project. It should be possible to adapt this script for other projects.

- When using the `--export-*` option to put the issues in GitHub, an API rate limit may apply. The script has some hardcoded delays,
however, GitHub may limit your API usage. If a rate limit occurs, the script retries every ten minutes. The script keeps track of the
migration status, so you may abort the script and retry at any time.

## License

Savane to GitHub Migration Tool is released under the GNU GPLv3.

Copyright 2021 Marius Greuel.
