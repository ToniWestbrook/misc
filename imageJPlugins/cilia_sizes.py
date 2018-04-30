# Copyright 2018, Anthony Westbrook <anthony.westbrook@unh.edu>, University of New Hampshire

# To install this script as a FIJI macro, perform the following steps:
#
#    1. From the "Plugins" menu, select "Install..."
#    2. Select this script (cilia_sizes.py)
#    3. Accept the default installation directory
#    4. Restart FIJI
#    5. The plugin will be available to run from the "Plugins" menu at the bottom

from ij import IJ, WindowManager
from ij.measure import ResultsTable
from fiji.util.gui import GenericDialogPlus
from trainableSegmentation import WekaSegmentation
import os

HEADER = "File\tProbability\tUnit\tIndex\tArea\tPerimeter\tMajor\tMinor\tAngle\tRatio"
RESULTS_FILE = "results.csv"
DEFAULT_DIR = ""
DEFAULT_TRAIN = ""

def registerWindow(passTitle, passWindows):
    passWindows.add(passTitle)
    IJ.selectWindow(passTitle)

def closeWindows(passWindows):
    for window in passWindows:
        IJ.selectWindow(window)
        IJ.run("Close")    
    
def setupMeasurements():                                                                                                                                                                                                                                                                             
    options = "area perimeter fit"        
    IJ.run("Set Measurements...", options)
        
def optionsDialog():
    dialog = GenericDialogPlus("Cilia Sizes")
    dialog.addDirectoryField("Image Directory", DEFAULT_DIR)
    dialog.addFileField("Training Model", DEFAULT_TRAIN)
    dialog.addStringField("Output Subdirectory", "output", 20)
    dialog.addStringField("Confocal Channel", "1", 20)
    dialog.addStringField("Probability Threshold", "0.67", 20)
    dialog.addStringField("Minimum Pixel Size", "2", 20)
    dialog.showDialog()
    
    # Check if canceled
    if dialog.wasCanceled(): return None
    
    textVals = [x.text for x in dialog.getStringFields()]
    
    return textVals

def prepareImage(passDir, passFile):
    # Attempt to open as image, exit if not
    fullPath = os.path.join(passDir, passFile)
    retImage = IJ.openImage(fullPath)
    if not retImage: return None
    retImage.show()
    
    return retImage

def finalizeImage(passImage):
    passImage.changes = False
    passImage.close()

def analyzeImage(passImage, passModel, passChannel, passProbability, passPixels, passOutput):
    retResults = list()
    windows = set()

    # Register current window
    registerWindow(passImage.title, windows)
    
    # Extract the requested channel
    IJ.run("Z Project...", "projection=[Max Intensity]");
    registerWindow("MAX_" + passImage.title, windows)
    IJ.run("Duplicate...", "title=temp")
    registerWindow("temp", windows)
    
    # Apply WEKA training model to image
    wekaSeg = WekaSegmentation(WindowManager.getCurrentImage())
    wekaSeg.loadClassifier(passModel)
    wekaSeg.applyClassifier(True)

    # Extract first slice of probability map
    wekaImg = wekaSeg.getClassifiedImage();
    wekaImg.show()
    registerWindow("Probability maps", windows)
    IJ.setSlice(1)
    IJ.run("Duplicate...", "title=temp2")
    registerWindow("temp2", windows)
    
    # Apply threshold and save
    IJ.setThreshold(passProbability, 1, "Black & White")
    fileParts = passImage.getTitle().split(".")
    IJ.save(os.path.join(passOutput, "{0}-probmap.png".format(fileParts[0], '.'.join(fileParts[1:]))))

    # Perform particle analysis and save
    IJ.run("Analyze Particles...", "size={0}-Infinity show=Outlines pixel clear".format(passPixels))
    registerWindow("Drawing of temp2", windows)
    IJ.save(os.path.join(passOutput, "{0}-particles.png".format(fileParts[0], '.'.join(fileParts[1:]))))
    
    # Get measurements
    tableResults = ResultsTable.getResultsTable()
    for rowIdx in range(tableResults.size()):
        retResults.append(tableResults.getRowAsString(rowIdx).split())
        retResults[-1].insert(0, WindowManager.getCurrentImage().getCalibration().unit)
        retResults[-1].append(float(retResults[-1][4])/float(retResults[-1][3]))

    # Close windows
    closeWindows(windows)
        
    return retResults

def processImages(passOptions):
    optImageDir = passOptions[0]
    optModel = passOptions[1]
    optOutput = passOptions[2]
    optChannel = int(passOptions[3])
    optProbability = 1.0 - float(passOptions[4])
    optPixels = int(passOptions[5])

    retResults = dict()
    
    # Iterate through all images in chosen directory
    root, dirs, files = next(os.walk(optImageDir))
    for curFile in files:
        # Prepare image
        curImage = prepareImage(root, curFile)
        if not curImage: continue
        
        # Analyze image
        retResults[curFile] = analyzeImage(curImage, optModel, optChannel, optProbability, optPixels, os.path.join(options[0], optOutput))
            
    return retResults

def writeResults(passResults, passOutput, passProbability):
    # Create results TSV
    with open(passOutput, "w") as fileHandle:
        fileHandle.write("{0}\n".format(HEADER))
        
        for image in passResults:
            for row in passResults[image]:
                fieldText = "\t".join(map(unicode, row))
                fileHandle.write(u"{0}\t{1}\t{2}\n".format(image, passProbability, fieldText).encode("utf8"))
            

# Setup measurements to record in CSV
setupMeasurements()

# Present user definable options, then process
options = optionsDialog()
if options:
    # Prepare output directory
    if not os.path.exists(os.path.join(options[0], options[2])):
        os.makedirs(os.path.join(options[0], options[2]))
    
    # Analyze images
    results = processImages(options)
    writeResults(results, os.path.join(options[0], options[2], RESULTS_FILE), options[4])
    IJ.showMessage("Analysis Complete!")        
