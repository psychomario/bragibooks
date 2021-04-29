from pathlib import Path
import audible, collections, html2text, getpass, os, readline, shutil
from datetime import datetime

### User editable variables
# for non-default m4b-tool install path
m4bpath = "m4b-tool"

# output dir
output = ""

# Number of cpus to use for jobs
cpus_to_use = ""
###

dir_path = Path(__file__).resolve().parent

def audible_login():
	print("You need to login")
	USERNAME = input("Email: ")
	PASSWORD = getpass.getpass()
	auth = audible.Authenticator.from_login(
		USERNAME,
		PASSWORD,
		locale="us",
		with_username=False,
		register=True
	)
	auth.to_file(Path(dir_path, ".aud_auth.txt"))

def audible_parser(asin):
	auth_file = Path(dir_path, ".aud_auth.txt")
	# Only proceed auth exists
	#TODO: add functional logged in state checking
	if auth_file.exists():
		auth = audible.Authenticator.from_file(auth_file)
		client = audible.Client(auth)
		ASIN = asin
		aud_json = client.get(
			f"catalog/products/{ASIN}",
			params={
				"response_groups": f'contributors,product_desc,product_extended_attrs,product_attrs',
				"asins": ASIN
			}
		)

		### JSON RESPONSE
		# We have:
		# Summary, Title, Author, Narrator, Series
		# Want: series number

		# metadata dictionary
		metadata_dict = {}

		## Title
		# Use subtitle if it exists
		if 'subtitle' in aud_json['product']:
			aud_title_start = aud_json['product']['title']
			aud_title_end = aud_json['product']['subtitle']
			metadata_dict['title'] = aud_title_start
			metadata_dict['subtitle'] = aud_title_end
		else:
			metadata_dict['title'] = aud_json['product']['title']

		## Summary
		aud_summary_json = aud_json['product']['merchandising_summary']
		metadata_dict['summary'] = html2text.html2text(aud_summary_json).replace("\n", " ")

		## Authors
		aud_authors_json = aud_json['product']['authors']
		# check if list contains more than 1 author
		if len(aud_authors_json) > 1:
			aud_authors_arr = []
			for narrator in range(len(aud_authors_json)):
				# from array of dicts, get author name
				aud_authors_arr.append(aud_authors_json[narrator]['name'])
			metadata_dict['authors'] = aud_authors_arr
		else:
			# else author name will be in first element dict
			metadata_dict['authors'] = [aud_authors_json[0]['name']]
		
		## Narrators
		aud_narrators_json = aud_json['product']['narrators']
		# check if list contains more than 1 narrator
		if len(aud_narrators_json) > 1:
			aud_narrators_arr = []
			for narrator in range(len(aud_narrators_json)):
				# from array of dicts, get narrator name
				aud_narrators_arr.append(aud_narrators_json[narrator]['name'])
			metadata_dict['narrators'] = aud_narrators_arr
		else:
			# else narrator name will be in first element dict
			metadata_dict['narrators'] = [aud_narrators_json[0]['name']]

		## Series
		# Check if book has publication name (series)
		if 'publication_name' in aud_json['product']:
			metadata_dict['series'] = aud_json['product']['publication_name']

		## Release date
		if 'release_date' in aud_json['product']:
			# Convert date string into datetime object
			metadata_dict['release_date'] = datetime.strptime(aud_json['product']['release_date'], '%Y-%m-%d').date()
		
		# return all data
		return metadata_dict
	else:
		print("no auth")
		# If no auth file exists, call login function
		audible_login()

def get_directory():
	# enable using tab for filename completion
	readline.set_completer_delims('')
	readline.parse_and_bind("tab: complete")

	# get dir from user
	input_take = input("Enter directory to use: ")

	if Path(input_take).is_dir():
		for dirpath, dirnames, files in os.walk(input_take):
			EXTENSIONS=['mp3', 'm4a', 'm4b']

			for EXT in EXTENSIONS:
				if collections.Counter(p.suffix for p in Path(dirpath).resolve().glob(f'*.{EXT}')):
					USE_EXT = EXT
					list_of_files = os.listdir(Path(dirpath))
					# Case for single file in a folder
					if len(list_of_files) == 1:
						dirpath = f"{dirpath}/" + list_of_files[0]
						num_of_files = 1
					else:
						num_of_files = sum(x.endswith(f'.{USE_EXT}') for x in list_of_files)

	elif Path(input_take).is_file():
		dirpath = Path(input_take)
		USE_EXT_PRE = dirpath.suffix
		USE_EXT = Path(USE_EXT_PRE).stem.split('.')[1]
		num_of_files = 1

	return Path(dirpath), USE_EXT, num_of_files

def m4b_data(input_data, metadata, output):
	## Checks
	# Find path to m4b-tool binary
	m4b_tool = shutil.which(m4bpath)

	# Check that binary actually exists
	if not m4b_tool:
		# try to automatically recover
		if shutil.which('m4b-tool'):
			m4b_tool = shutil.which('m4b-tool')
		else:
			raise SystemExit('Error: Cannot find m4b-tool binary.')
	# If no response from binary, exit
	if not m4b_tool:
		raise SystemExit('Error: Could not successfully run m4b-tool, exiting.')

	if not output:
		print("Defaulting output to home directory")
		default_output = Path.home()
		output = Path(f"{default_output}/output")
	#

	## Metadata variables
	# Only use subtitle in case of metadata, not file name
	if 'subtitle' in metadata:
		m.title = metadata['title']
		m.subtitle = metadata['subtitle']
		title = f'{m.title} - {m.subtitle}'
	else:
		title = metadata['title']
	# Only use first author/narrator for file names; no subtitle for file name
	path_title = metadata['title']
	path_author = metadata['authors'][0]
	path_narrator = metadata['narrators'][0]
	# For embedded, use all authors/narrators
	author = ', '.join(metadata['authors'])
	narrator = ', '.join(metadata['narrators'])
	series = metadata['series']
	summary = metadata['summary']
	year = metadata['release_date'].year

	book_output = f"{output}/{path_author}/{path_title}"
	##

	## File variables
	in_dir = input_data[0]
	in_ext = input_data[1]
	num_of_files = input_data[2]
	##

	# Available CPU cores to use
	if not cpus_to_use:
		num_cpus = os.cpu_count()
	else:
		num_cpus = cpus_to_use

	# Make necessary directories
	Path(book_output).mkdir(parents=True, exist_ok=True)

	## Array for argument use
	# args for multiple input files in a folder
	if Path(in_dir).is_dir() and num_of_files > 1:
		print("Got multiple files in a dir")
		args = [
			' merge',
			f"--output-file=\"{book_output}/{title}.m4b\"",
			f'--name=\"{title}\"',
			f'--album=\"{path_title}\"',
			f'--artist=\"{narrator}\"',
			f'--albumartist=\"{author}\"',
			f'--year=\"{year}\"',
			f'--description=\"{summary}\"',
			'--force',
			'--no-chapter-reindexing',
			'--no-cleanup',
			f'--jobs={num_cpus}'
		]
		if series:
			args.append(f'--series \"{series}\"')

		# m4b command with passed args
		m4b_cmd = m4b_tool + ' '.join(args) + f' \"{in_dir}\"'
		os.system(m4b_cmd)

		m4b_fix_chapters(f"{book_output}/{title}.chapters.txt", f"{book_output}/{title}.m4b", m4b_tool)

	# args for single m4b input file
	elif Path(in_dir).is_file() and in_ext == "m4b":
		print("got single m4b input")
		m4b_cmd = m4b_tool + ' meta ' + f'--export-chapters=\"\"' + f' \"{in_dir}\"'
		os.system(m4b_cmd)
		shutil.move(f"{in_dir.parent}/{in_dir.stem}.chapters.txt", f"{book_output}/{title}.chapters.txt")

		args = [
			' meta',
			f'--name=\"{title}\"',
			f'--album=\"{path_title}\"',
			f'--artist=\"{narrator}\"',
			f'--albumartist=\"{author}\"',
			f'--year=\"{year}\"',
			f'--description=\"{summary}\"'
		]

		# make backup file
		shutil.copy(in_dir, f"{in_dir.parent}/{in_dir.stem}.new.m4b")

		# m4b command with passed args
		m4b_cmd = m4b_tool + ' '.join(args) + f" \"{in_dir.parent}/{in_dir.stem}.new.m4b\""
		os.system(m4b_cmd)

		# Move completed file
		shutil.move(f"{in_dir.parent}/{in_dir.stem}.new.m4b", f"{book_output}/{title}.m4b")

		m4b_fix_chapters(f"{book_output}/{title}.chapters.txt", f"{book_output}/{title}.m4b", m4b_tool)

	elif not in_ext:
		print(f"No recognized filetypes found for {title}")

def m4b_fix_chapters(input, target, m4b_tool):
	new_file_content = ""
	with open(input) as f:
		# Store and then skip past total length section
		for line in f:
			if "# total-length" in line.strip():
				new_file_content += line.strip() +"\n"
				break
		# Iterate over rest of the file
		counter = 0
		for line in f:
			stripped_line = line.strip()
			counter += 1
			new_line = (stripped_line[0:13]) + f'Chapter {"{0:0=2d}".format(counter)}'
			new_file_content += new_line +"\n"

	with open(input, 'w') as f:
		f.write(new_file_content)
	
	# Apply fixed chapters to file
	m4b_chap_cmd = m4b_tool + ' meta ' + f" \"{target}\" " + f"--import-chapters=\"{input}\""
	os.system(m4b_chap_cmd)

def call():
	input_data = get_directory()
	asin = input("Audiobook ASIN: ")
	metadata = audible_parser(asin)
	m4b_data(input_data, metadata, output)

call()