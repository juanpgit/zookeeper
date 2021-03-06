import os
import sys
import zookeeper
import win32com.client
from win32com.client import constants
from PySide import QtCore, QtGui

def XSILoadPlugin( in_reg ):
  in_reg.Author = "Helge Mathee"
  in_reg.Name = "ZooKeeperPlugin"
  in_reg.Major = 1
  in_reg.Minor = 0

  in_reg.RegisterCommand("zkSubmit","zkSubmit")
  in_reg.RegisterCommand("zkShowManager","zkShowManager")
  in_reg.RegisterCommand("zkSynchSceneToNetwork","zkSynchSceneToNetwork")
  in_reg.RegisterMenu(constants.siMenuMainTopLevelID,"ZooKeeper",False,False)

  return True

def XSIUnloadPlugin( in_reg ):
  strPluginName = in_reg.Name
  Application.LogMessage(str(strPluginName) + str(" has been unloaded."),constants.siVerbose)
  return True

def zkSubmit_Init( in_ctxt ):
  oCmd = in_ctxt.Source
  oCmd.Description = ""
  oCmd.ReturnValue = True
  return True

def zkSubmit_Execute(  ):
  conn = zookeeper.zkDB.zkConnection(debug = False)
  submitter = zookeeper.zkClient.zkSoftimageSubmitter(conn, Application, constants)
  submitter.submitWithDialog()
  return True

def zkShowManager_Init( in_ctxt ):
  oCmd = in_ctxt.Source
  oCmd.Description = ""
  oCmd.ReturnValue = True
  return True

def zkShowManager_Execute(  ):
  conn = zookeeper.zkDB.zkConnection(debug = False)
  app = zookeeper.zkUI.zkApp()
  consumer = zookeeper.zkClient.zkManager(conn)
  app.exec_()
  return True

def zkSynchSceneToNetwork_Init( in_ctxt ):
  oCmd = in_ctxt.Source
  oCmd.Description = ""
  oCmd.ReturnValue = True
  return True

def zkSynchSceneToNetwork_Execute(  ):
  app = zookeeper.zkUI.zkApp()

  projectPath = Application.ActiveProject.Path
  sourceFolder = projectPath

  # ------------------------- Juan modified START -------------------------
  # this is Juan project specific...
  import linecache
  fileToRead = r"R:\_JPstuff_actually_\Dropbox\JPB_2D3D_share\tools\zookeeper\zookeeper_sync_data.txt"

  jpbLocalFolder = linecache.getline( fileToRead, 1 )
  jpbSyncFolder = linecache.getline( fileToRead, 2 )
  jpbLocalFolder = jpbLocalFolder.strip()
  jpbSyncFolder = jpbSyncFolder.strip()

  jpbTargetProject = projectPath.replace( jpbLocalFolder, jpbSyncFolder)
  jpbTargetProject = jpbTargetProject + '_SYNC'

  # build up the UI
  fields = []
  fields += [{'name': 'sourceProject', 'value': sourceFolder, 'type': 'folder', 'tooltip': 'The source project for the sync.', 'readonly': True}]
  fields += [{'name': 'targetProject', 'value': jpbTargetProject, 'type': 'folder', 'tooltip': 'The target project for the sync.'}]
  fields += [{'name': 'createProject', 'value': False, 'type': 'bool', 'tooltip': 'If checked a project will be created in the targetProject location.'}]
  fields += [{'name': 'sourceFolder', 'value': jpbLocalFolder, 'type': 'folder', 'tooltip': 'OPTIONAL: The source folder for the sync. Can be the project folder or levels higher up.'}]
  fields += [{'name': 'targetFolder', 'value': jpbSyncFolder, 'type': 'folder', 'tooltip': 'OPTIONAL: The target folder for the sync. Can be the network folder or levels higher up.'}]
 
  # ------------------------- Juan modified END -------------------------

  hook = zookeeper.zkClient.zkSoftimageLogHook(Application)
  sys.stdout = hook
  sys.stderr = hook

  def onAccepted(fields):
    conn = None
    validUncPaths = []
    scene = Application.ActiveProject.ActiveScene
    clips = scene.ImageClips
    scenePathName = str(scene.FileName.Value)
    externalFiles = scene.ExternalFiles
    pathsToSynch = []
    pathsToAdapt = []
    pathsHit = {}
    for i in range(externalFiles.Count):
      externalFile = externalFiles(i)
      resolvedPath = externalFile.ResolvedPath

      # invalid rigid body cache
      if resolvedPath.lower().endswith('rigidbodycache.xsi'):
        continue

      if pathsHit.has_key(resolvedPath):
        index = pathsHit[resolvedPath]
        pathsToAdapt[index] += [{'obj': externalFile, 'type': 'ExternalFile'}]
        continue

      # for textures etc below referenced models
      # we will need to ensure that the user does not have models in the scene which 
      # are not on shared storages
      if externalFile.FileType != 'Models':
        owner = externalFile.Owners(0)
        if owner:
          if owner.IsLocked():
            if not conn:
              conn = zookeeper.zkDB.zkConnection(debug = False)
              uncPathFieldList = zookeeper.zkDB.zkValidUnc.getFieldList(conn, 'path')
              for uncPath in uncPathFieldList:
                validUncPaths += [uncPath[1]]          

            messageCaption = str(owner)
            source = owner.Parent
            if source.Type == 'ImageSource':
              for j in range(clips.Count):
                clip = clips(j)
                if not str(clip.Source) == str(source):
                  continue
                material = clip.Owners(1)
                messageCaption = str(material.Owners(1)).partition('.')[0]

            if not zookeeper.zkClient.zk_validateNetworkFilePath(resolvedPath, validUncPaths, shouldExist = True):
              QtGui.QMessageBox.critical(None, 'ZooKeeper Error', 'The referenced model\n%s"\ncontains some paths which are not pointing\nto shared storage. Please correct the referenced model by moving the files\nmanually and update the paths manually as well.' % messageCaption)
              return False

            continue

      pathsHit[resolvedPath] = len(pathsToSynch)
      pathsToSynch += [resolvedPath]
      pathsToAdapt += [[{'obj': externalFile, 'type': 'ExternalFile'}]]

    # here you can add additional files, they need to be added in the format of
    # pathsToSynch += [resolvedPathOnDisc]
    # pathsToAdapt += [[{'obj': xsiObjectToUpdate, 'type': 'MyType'}]]
    utils = XSIUtils
    envs = scene.SimulationEnvironments
    if envs.Count > 0:
      env = envs(0)
      simCtrl = env.SimulationTimeControl
      offset = simCtrl.offset.Value
      duration = simCtrl.duration.Value
      caches = env.Caches
      for i in range(caches.Count):
        cache = caches(i)
        items = cache.SourceItems
        for j in range(items.Count):
          item = items(j)
          try:
            target = Application.Dictionary.GetObject(item.Target)
          except:
            continue
          path = simCtrl.FilePath.Value
          path += simCtrl.FileName.Value
          path += simCtrl.FileTypeString.Value
          tokenNames = []
          tokenValues = []
          tokenNames += ['model']
          tokenValues += [target.Model.Name]
          tokenNames += ['object']
          tokenValues += [target.Parent3DObject.Name]
          tokenNames += ['version']
          tokenValues += [simCtrl.VersionString.Value]

          for frame in range(int(offset), int(duration)+2):
            resolvedPath = utils.ResolveTokenString(path, frame, False, tokenNames, tokenValues)
            pathsToSynch += [resolvedPath]
            pathsToAdapt += [[{'obj': item, 'type': 'ICECache'}]]


    sourceProject = fields[0]['value']
    targetProject = fields[1]['value']
    createProject = fields[2]['value']
    sourceFolder = fields[3]['value']
    targetFolder = fields[4]['value']

    if targetProject == '':
      QtGui.QMessageBox.warning(None, 'ZooKeeper Warning', 'No target project specified.')
      return False

    if sourceFolder == '':
      sourceFolder = sourceProject
    if targetFolder == '':
      targetFolder = targetProject

    if createProject:
      Application.ActiveProject2 = Application.CreateProject2(targetProject)

    # create progessbar for file syncing
    progBarFileSync = XSIUIToolkit.ProgressBar
    progBarMax = len(pathsToSynch)

    progBarFileSync.Maximum = progBarMax
    progBarFileSync.Step = 1
    progBarFileSync.Caption = "syncing..."

    progBarFileSync.Visible = True

    def callFuncProgBar( **info ):
      msg = info.get("message", "")
      LogMessage( msg )
      tmpFileName = info.get("fileName", "")
      tmpFileName = os.path.basename( tmpFileName )
      progBarFileSync.StatusText = "%s   -   %s / %s" % (tmpFileName, progBarFileSync.Value, progBarMax)
      progBarFileSync.Increment()

    synchedPaths = zookeeper.zkClient.zk_synchronizeFilesBetweenFolders(pathsToSynch, sourceFolder, targetFolder, logFunc = callFuncProgBar)

    # make sure the progress bar disappears
    progBarFileSync.Visible = False

    for i in range(len(pathsToAdapt)):
      if synchedPaths[i] is None:
        continue
      for pathToAdapt in pathsToAdapt[i]:

        if pathToAdapt['type'] == 'ExternalFile':

          pathToAdapt['obj'].Path = synchedPaths[i]


        # here you can add other cases for your own file object types
        # elif pathToAdapt['type'] == 'MyType':
        #   pathToAdapt['obj'].filePathParam.Value = synchedPaths[i]

    relScenePath = os.path.relpath(scenePathName, sourceProject)
    Application.SaveSceneAs(os.path.join(targetProject, relScenePath))

    message = "The scene is now in the target location. It has been saved as\n\n"
    message += os.path.normpath(os.path.join(targetProject, relScenePath))
    message += "\n\nYou can submit this scene for rendering now."
    QtGui.QMessageBox.information(None, 'ZooKeeper', message)

  dialog = zookeeper.zkUI.zkFieldsDialog(fields, onAcceptedCallback = onAccepted, onRejectedCallback = None)
  dialog.setMinimumWidth(600)
  dialog.exec_()

  return True

def ZooKeeper_Init( in_ctxt ):
  oMenu = in_ctxt.Source
  oMenu.AddCommandItem("ZooKeeper Submit","zkSubmit")
  oMenu.AddSeparatorItem()
  oMenu.AddCommandItem("ZooKeeper Manager","zkShowManager")
  oMenu.AddSeparatorItem()
  oMenu.AddCommandItem("Synch Scene to Network","zkSynchSceneToNetwork")
  return True
