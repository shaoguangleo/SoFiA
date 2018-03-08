#! /usr/bin/env python

import numpy as np
from .functions import *
import sys
import math

# Function to read in a cube and scale it by the RMS.
# This script is useful to correct for variation in noise as function of frequency, noisy edges of cubes and channels with strong RFI.

def sigma_scale(cube, scaleX=False, scaleY=False, scaleZ=True, edgeX=0, edgeY=0, edgeZ=0, statistic="mad", fluxRange="all", method="global", windowSpatial=20, windowSpectral=20, gridSpatial=10, gridSpectral=10):
	"""
	Sigma scaling only works for 3D cubes, as it is mainly designed to correct for differences in frequency.
	
	Parameters
	----------
	  cube:            The input cube.
	  scaleX,Y,Z:      True or False to choose which axis should be scaled.
	  edgeX,Y,Z:       The edges of the cube that are excluded from the noise calculation (default: 0,0,0).
	  statistic:       Which algorithm to use: "negative", "mad" or "std" (default: "mad").
	  method:          "local"   Measure local rms on specified grid.
	                   "global"  Measure RMS in entire planes perpendicular to the axis being scaled.
	  windowSpatial:   Spatial window size over which to measure local RMS. Must be even.
	  windowSpectral:  Spectral window size over which to measure local RMS. Must be even.
	  gridSpatial:     Size of each spatial grid cell for local RMS measurement. Must be even.
	  gridSpectral:    Size of each spectral grid cell for local RMS measurement. Must be even.
	"""
	
	verbose = 0
	
	# Ensure that window and grid sizes are greater than 0 and divisible by 2
	windowSpatial  = max(windowSpatial, 2)
	windowSpectral = max(windowSpatial, 2)
	gridSpatial    = max(gridSpatial, 2)
	gridSpectral   = max(gridSpectral, 2)
	windowSpatial  += windowSpatial % 2
	windowSpectral += windowSpectral % 2
	gridSpatial    += gridSpatial % 2
	gridSpectral   += gridSpectral % 2
	
	# Divide window sizes by 2 to get radii
	windowSpatial  /= 2
	windowSpectral /= 2
	
	sys.stdout.write("Generating noise-scaled data cube:\n")
	
	if statistic == "mad": sys.stdout.write("Applying Median Absolute Deviation (MAD) statistic.\n")
	if statistic == "std": sys.stdout.write("Applying Standard Deviation (STD) statistic.\n")
	if statistic == "negative": sys.stdout.write("Applying Negative statistic.\n")
	sys.stdout.flush()
	
	# Check the dimensions of the cube (could be obtained from header information)
	dimensions = np.shape(cube)
	
	# Define the range over which statistics are calculated
	z1 = edgeZ
	z2 = dimensions[0] - edgeZ
	y1 = edgeY
	y2 = dimensions[1] - edgeY
	x1 = edgeX
	x2 = dimensions[2] - edgeX
	
	if z1 >= z2 or y1 >= y2 or x1 >= x2:
		sys.stderr.write("ERROR: Edge size exceeds cube size for at least one axis.\n")
		sys.exit(1)
	
	# LOCAL noise measurement within running window (slow and memory-intensive)
	if method == "local":
		# Create empty cube (filled with 0) to hold noise values
		rms_cube = np.zeros(cube.shape)
		
		# Create grid to be used
		gridPointsZ = np.arange((dimensions[0] - gridSpectral * (int(math.ceil(float(dimensions[0]) / float(gridSpectral))) - 1)) / 2, dimensions[0], gridSpectral)
		gridPointsY = np.arange((dimensions[1] - gridSpatial  * (int(math.ceil(float(dimensions[1]) / float(gridSpatial)))  - 1)) / 2, dimensions[1], gridSpatial)
		gridPointsX = np.arange((dimensions[2] - gridSpatial  * (int(math.ceil(float(dimensions[2]) / float(gridSpatial)))  - 1)) / 2, dimensions[2], gridSpatial)
		gridPoints = []
		for z in gridPointsZ:
			for y in gridPointsY:
				for x in gridPointsX:
					gridPoints.append((z, y, x))
		
		# Divide grid sizes by 2 to get radii
		gridSpatial /= 2
		gridSpectral /= 2
		
		# Create grid cell and window list
		gridList = []
		windowList = []
		for z in gridPointsZ:
			for y in gridPointsY:
				for x in gridPointsX:
					gridList.append((max(0, z - gridSpectral), min(dimensions[0], z + gridSpectral), max(0, y - gridSpatial), min(dimensions[1], y + gridSpatial), max(0, x - gridSpatial), min(dimensions[2], x + gridSpatial)))
					windowList.append((max(0, z - windowSpectral), min(dimensions[0], z + windowSpectral), max(0, y - windowSpatial), min(dimensions[1], y + windowSpatial), max(0, x - windowSpatial), min(dimensions[2], x + windowSpatial)))
		
		# Iterate over data cube
		for grid, window in list(zip(gridList, windowList)):
			if not np.all(np.isnan(cube[window[0]:window[1], window[2]:window[3], window[4]:window[5]])):
				rms_cube[grid[0]:grid[1], grid[2]:grid[3], grid[4]:grid[5]] = GetRMS(cube[window[0]:window[1], window[2]:window[3], window[4]:window[5]], rmsMode=statistic, fluxRange=fluxRange, zoomx=1, zoomy=1, zoomz=1, verbose=verbose)
		
		# Divide data cube by local RMS cube
		cube /= rms_cube
		
		# Delete the RMS cube to release its memory
		del rms_cube
	
	# GLOBAL noise measurement of entire 2-D plane (much faster and more memory-friendly)
	else:
		if scaleZ:
			for i in range(dimensions[0]):
				if not np.all(np.isnan(cube[i, y1:y2, x1:x2])):
					rms = GetRMS(cube[i, y1:y2, x1:x2], rmsMode=statistic, fluxRange=fluxRange, zoomx=1, zoomy=1, zoomz=1, verbose=verbose)
					if rms > 0: cube[i, :, :] /= rms
		
		if scaleY:
			for i in range(dimensions[1]):
				if not np.all(np.isnan(cube[z1:z2, i, x1:x2])):
					rms = GetRMS(cube[z1:z2, i, x1:x2], rmsMode=statistic, fluxRange=fluxRange, zoomx=1, zoomy=1, zoomz=1, verbose=verbose)
					if rms > 0: cube[:, i, :] /= rms
		
		if scaleX:
			for i in range(dimensions[2]):
				if not np.all(np.isnan(cube[z1:z2, y1:y2, i])):
					rms = GetRMS(cube[z1:z2, y1:y2, i], rmsMode=statistic, fluxRange=fluxRange, zoomx=1, zoomy=1, zoomz=1, verbose=verbose)
				if rms > 0: cube[:, :, i] /= rms
	
	sys.stdout.write("Noise-scaled data cube generated.\n\n")
	sys.stdout.flush()
	
	return cube
