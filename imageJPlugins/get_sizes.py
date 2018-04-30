# Copyright 2017, Anthony Westbrook <anthony.westbrook@unh.edu>, University of New Hampshire

# To install this script as a FIJI macro, perform the following steps:
# 
#    1. From the "Plugins" menu, select "Install..."
#    2. Select this script (get_sizes.py)
#    3. Accept the default installation directory
#    4. Restart FIJI
#    5. The plugin will be available to run from the "Plugins" menu at the bottom

from ij import IJ, WindowManager
from ij.measure import ResultsTable
from fiji.util.gui import GenericDialogPlus 
import math
import sys
import os

HEADER = "File\tThreshold\tAngle\tMaximum\tArea\tStdDev\tPerimeter\tRectX\tRectY\tWidth\tHeight\tCircularity\tAR\tRoundness\tSolidity"
THRESHOLDS = ["Default", "Huang", "Percentile"]
RESULTS_FILE = "results.csv"

FIELD_IDX = 0
FIELD_AREA = 1
FIELD_PERIMETER = 3
FIELD_WIDTH = 6
FIELD_HEIGHT = 7
FIELD_CIRCLE = 8
FIELD_ROUND = 10
FIELD_SOLID = 11

def setupMeasurements():
	options = "area standard bounding perimeter shape"	
	IJ.run("Set Measurements...", options)

def optionsDialog():
	dialog = GenericDialogPlus("Automated Size Analysis")
	dialog.addDirectoryField("Image Directory", "")
	dialog.addStringField("Output Subdirectory", "output", 20)
	dialog.addStringField("Minimum Pixel Size", "50000", 20)
	dialog.addStringField("Minimum Roundness", "0.4", 20)
	dialog.addStringField("Gaussian Blur", "6", 20)
	dialog.addStringField("Rotation Steps", "3", 20)
        dialog.addStringField("Thresholds", ",".join(THRESHOLDS), 20)
	dialog.addCheckbox("Rotate Images", True)
	dialog.addCheckbox("Multiple Thresholds", True)
	dialog.showDialog()

	# Check if canceled
	if dialog.wasCanceled(): return None

	textVals = [x.text for x in dialog.getStringFields()]
	boolVals = [x.getState() for x in dialog.getCheckboxes()]

	return textVals + boolVals

def prepareImage(passDir, passFile, passOutput, passPixels, passBlur, passThreshold):
	# Attempt to open as image, exit if not
	fullPath = os.path.join(passDir, passFile)
	retImage = IJ.openImage(fullPath)
	if not retImage: return None
	retImage.show()

	# Resize canvas to prepare for fast rotations, select original
	imgWidth = retImage.getWidth()
	imgHeight = retImage.getHeight()
	maxDim = math.sqrt(imgWidth ** 2 + imgHeight ** 2)
	borderX = (maxDim - imgWidth)/2
	borderY = (maxDim - imgHeight)/2
	
	IJ.run("Canvas Size...", "width={0} height={0} position=Center".format(maxDim))
	IJ.makeRectangle(borderX, borderY, imgWidth, imgHeight) 

	# Set scale to pixels (will manually calculate later)
	IJ.run("Set Scale...", "distance=0 known=0 pixel=1 unit=pixel");

	# Blur "overhanging" projections
	IJ.run("Gaussian Blur...", "sigma={0}".format(passBlur))
	
	# Set threshold 
	IJ.setAutoThreshold(retImage, "{0} dark apply".format(passThreshold))
	IJ.makeRectangle(0, 0, retImage.getWidth(), retImage.getHeight()) 
		
	# Analyze particles and obtain outline image
	IJ.run("Analyze Particles...", "size={0}-Infinity show=Outlines pixel clear".format(passPixels));
	IJ.selectWindow("Drawing of {0}".format(retImage.getTitle()))
	
	fileParts = passFile.split(".")
	IJ.save(os.path.join(passOutput, "{0}-outline-{1}.{2}".format(fileParts[0], passThreshold, '.'.join(fileParts[1:]))))
	IJ.run("Close")

	return retImage

def finalizeImage(passImage):
	passImage.changes = False
	passImage.close()

def measureImage(passImage, passPixels, passSteps):
	retResults = list()
	
	# Analyze particles
	IJ.run("Analyze Particles...", "size={0}-Infinity show=Nothing pixel display clear include".format(passPixels));
	
	# Obtain results (initialize if first iteration)
	tableResults = ResultsTable.getResultsTable()
	for rowIdx in range(tableResults.size()):		
		retResults.append(tableResults.getRowAsString(rowIdx).split())

	# Rotate
	IJ.run("Rotate... ", "angle={0} interpolation=Bilinear".format(passSteps))

	return retResults
	
def processImages(passOptions):
	optImageDir = passOptions[0]
	optOutput = passOptions[1]
	optPixels = int(passOptions[2])
	optRoundness = float(passOptions[3])
	optBlur = int(passOptions[4])
	optSteps = int(passOptions[5])
        optThresholdTypes = passOptions[6].split(',')
	optRotate = passOptions[7]
	optThresholdActive = passOptions[8]

	retResults = dict()
	
	# Ready options for iteration
        print("TEST")
	thresholds = (THRESHOLDS[0:1], optThresholdTypes)[optThresholdActive]
	rotations = range(0, (1, 90)[optRotate], optSteps)
		
	# Iterate through all images in chosen directory
	root, dirs, files = next(os.walk(optImageDir))
	for curFile in files:
		# Start record for file
		retResults[curFile] = dict()
		
		for threshold in thresholds:
			# Start record for threshold
			retResults[curFile][threshold] = dict()
			
			# Prepare image
			curImage = prepareImage(root, curFile, os.path.join(root, optOutput), optPixels, optBlur, threshold)
			if not curImage: continue

			# Rotate and record
			for rotation in rotations:
				# Start record for rotation
				retResults[curFile][threshold][rotation] = dict()
				
				results = measureImage(curImage, optPixels, optSteps)

				# Filter minimum roundness
				for result in results:
					if float(result[FIELD_ROUND]) < optRoundness: continue

					# Record result for particle (only handles single particle currently)
					#retResults[curFile][threshold][rotation][result[FIELD_IDX]] = result
					retResults[curFile][threshold][rotation][0] = result
						
					#print("{0} {1} {2}: {3}".format(curFile, threshold, rotation, result))

			# Close image
			finalizeImage(curImage)

	return retResults

def writeResults(passResults, passOutput):
	winners = dict()
	
	# Pick winner per image
	for image in passResults:
		# Pick best threshold
		maxThreshold = [THRESHOLDS[0], 0.0]
		for threshold in passResults[image]:
			for rotation in passResults[image][threshold]:
				particleAvg = [0, 0]
				for particle in passResults[image][threshold][rotation]:
					fields = passResults[image][threshold][rotation][particle]
					particleAvg[0] += (float(fields[FIELD_SOLID]) + float(fields[FIELD_CIRCLE]))/2
					particleAvg[1] += 1

				# If threshold resulted in no particles, skip
				if (particleAvg[1] == 0): continue
				
				curAvg = float(particleAvg[0]) / float(particleAvg[1])				
				if curAvg > maxThreshold[1]:
					maxThreshold[0] = threshold
					maxThreshold[1] = curAvg

		# Pick the longest dimension (based off particle #1)
		for threshold in passResults[image]:		
			maxRotation = [0, 0]
			#for rotation in passResults[image][maxThreshold[0]]:
			for rotation in passResults[image][threshold]:
				# If particle #1 not present, skip
				if not 0 in passResults[image][threshold][rotation]: continue
				
				fields = passResults[image][threshold][rotation][0]

				# Check threshold max
				if int(fields[FIELD_WIDTH]) > maxRotation[1]:
					maxRotation[0] = rotation
					maxRotation[1] = int(fields[FIELD_WIDTH])
	
				if int(fields[FIELD_HEIGHT]) > maxRotation[1]:
					maxRotation[0] = rotation
					maxRotation[1] = int(fields[FIELD_HEIGHT])

			winners.setdefault(image, dict())	
			winners[image][threshold] = (maxRotation[0], maxThreshold[0])

	# Create results TSV
	with open(passOutput, "w") as fileHandle:
		fileHandle.write("{0}\n".format(HEADER))

		for image in passResults:
			for threshold in passResults[image]:
				for rotation in passResults[image][threshold]:
					for particle in passResults[image][threshold][rotation]:
						# Detect if winner
						winText = "False"
						if image in winners and threshold in winners[image]:
							if winners[image][threshold][0] == rotation:
								if winners[image][threshold][1] == threshold: 
									winText = "Image"
								else: 
									winText = "Threshold"

						fieldText = "\t".join(passResults[image][threshold][rotation][particle][1:])
						fileHandle.write("{0}\t{1}\t{2}\t{3}\t{4}\n".format(image, threshold, rotation, winText, fieldText))
			
# Setup measurements to record in CSV
setupMeasurements()

# Present user definable options, then process
options = optionsDialog()
if options: 
	# Prepare output directory
	if not os.path.exists(os.path.join(options[0], options[1])):
		os.makedirs(os.path.join(options[0], options[1]))

	results = processImages(options)
	writeResults(results, os.path.join(options[0], options[1], RESULTS_FILE))
	print("Analysis Complete!")
