from pathlib import Path
import shutil
import os
import csv
import tqdm


TARGET_PATH = Path("commonvoice")


def main(source, dest):
	with open(source/"validated.tsv") as cv_file, open(dest/"clips.tsv", "w") as res_file:
		writer = csv.writer(res_file, delimiter="\t")
		for row in tqdm.tqdm(csv.DictReader(cv_file, delimiter="\t")):
			if os.path.exists(source/"clips"/row["path"]):
				shutil.copy(source/"clips"/row["path"], dest/row["path"])
				writer.writerow([dest/row["path"], row["sentence"]])
			else:
				print("Skipping", source/"clips"/row["path"])

if __name__ == "__main__":
	import sys
	if len(sys.argv) <= 2:
		print("Not enough arguments.")
		print(f"Usage: {sys.argv[0]} <dir> <lang>")
		sys.exit(1)
	main(Path(sys.argv[1])/sys.argv[2], TARGET_PATH/sys.argv[2])