-- SPDX-License-Identifier: GPL-2.0-only
on resourcePath()
	return (POSIX path of (path to me)) & "Contents/Resources/"
end resourcePath

on run
	try
		set mapFile to choose file with prompt "Choose a Freeplane mind map to export:"
		set mapPath to POSIX path of mapFile
		if mapPath does not end with ".mm" then error "The selected file must have a .mm extension."
		my exportMap(mapPath)
	on error errorMessage number errorNumber
		if errorNumber is not -128 then display alert "Interactive HTML export failed" message errorMessage as critical
	end try
end run

on open droppedItems
	if (count of droppedItems) is not 1 then
		display alert "Choose one mind map" message "Drop one .mm file on the app at a time." as warning
		return
	end if
	try
		set mapPath to POSIX path of (item 1 of droppedItems)
		if mapPath does not end with ".mm" then error "The selected file must have a .mm extension."
		my exportMap(mapPath)
	on error errorMessage number errorNumber
		if errorNumber is not -128 then display alert "Interactive HTML export failed" message errorMessage as critical
	end try
end open

on exportMap(mapPath)
	set freeplaneApp to my findFreeplane()
	set mapName to do shell script "/usr/bin/basename " & quoted form of mapPath
	set defaultName to (text 1 thru -4 of mapName) & ".html"
	set htmlFile to choose file name with prompt "Save the Interactive HTML export:" default name defaultName
	set htmlPath to POSIX path of htmlFile
	set exporter to my resourcePath() & "bin/export-map.sh"
	set freeplaneHome to freeplaneApp & "/Contents/app"
	set commandLine to "/usr/bin/env FREEPLANE_HOME=" & quoted form of freeplaneHome & " " & quoted form of exporter & " " & quoted form of mapPath & " " & quoted form of htmlPath
	try
		do shell script commandLine
	on error errorMessage number errorNumber
		error "The export could not be completed. " & errorMessage number errorNumber
	end try
	do shell script "/usr/bin/open " & quoted form of htmlPath
end exportMap

on findFreeplane()
	set candidates to {"/Applications/Freeplane.app", (POSIX path of (path to home folder)) & "Applications/Freeplane.app"}
	repeat with candidate in candidates
		set candidatePath to contents of candidate
		if my validFreeplane(candidatePath) then return candidatePath
	end repeat
	try
		set selectedApp to choose application with prompt "Choose the installed Freeplane application:" as alias
		set selectedPath to POSIX path of selectedApp
		if my validFreeplane(selectedPath) then return selectedPath
		error "The selected application does not contain Contents/app/freeplanelauncher.jar. Choose the installed Freeplane.app bundle."
	on error errorMessage number errorNumber
		if errorNumber is -128 then error errorMessage number errorNumber
		error errorMessage number errorNumber
	end try
end findFreeplane

on validFreeplane(appPath)
	set launcher to appPath & "/Contents/app/freeplanelauncher.jar"
	try
		do shell script "/usr/bin/test -f " & quoted form of launcher
		return true
	on error
		return false
	end try
end validFreeplane
