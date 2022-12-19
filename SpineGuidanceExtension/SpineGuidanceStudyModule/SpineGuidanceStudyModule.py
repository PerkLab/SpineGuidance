import logging
import os
from xml.etree.ElementTree import QName
import numpy as np
import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin


#
# SpineGuidanceStudyModule
#

class SpineGuidanceStudyModule(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Spine guidance simulation study"
    self.parent.categories = ["Ultrasound"]
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["David Morton (Perk Lab)"]
    self.parent.helpText = """
        This module facilitates simulated needle placement in the context of previously scanned images or volumes.
        See more information in <a href="https://github.com/PerkLab/SpineGuidance">module documentation</a>.
        """
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
        This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
        and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
        """

    # Additional initialization step after application startup is complete
    # slicer.app.connect("startupCompleted()", registerSampleData)


#
# SpineGuidanceStudyModuleWidget
#

class SpineGuidanceStudyModuleWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  LAYOUT_DUAL3D = 101

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/SpineGuidanceStudyModule.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = SpineGuidanceStudyModuleLogic()
    self.logic.setupScene()

    self.setupCustomLayout()

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.taskSelector.connect('currentPathChanged(QString)', self.onTaskChanged)
    # Scene selection
    self.ui.previousButton.connect('clicked(bool)', self.onPreviousButton)
    self.ui.nextButton.connect('clicked(bool)', self.onNextButton)

    self.ui.resetNeedleButton.connect('clicked(bool)', self.onResetNeedleButton)
    self.ui.resetViewsButton.connect('clicked(bool)', self.resetViews)

    self.ui.usVolumeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onUsVolumeSelected)
    self.ui.needleTransformComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onNeedleTransformSelected)

    # Translation

    self.ui.leftButton.connect('clicked(bool)', self.onLeftButton)
    self.ui.rightButton.connect('clicked(bool)', self.onRightButton)
    self.ui.upButton.connect('clicked(bool)', self.onUpButton)
    self.ui.downButton.connect('clicked(bool)', self.onDownButton)
    self.ui.inButton.connect('clicked(bool)', self.onInButton)
    self.ui.outButton.connect('clicked(bool)', self.onOutButton)
    self.ui.needleInLargeButton.connect('clicked(bool)', self.onInLargeButton)
    self.ui.needleOutLargeButton.connect('clicked(bool)', self.onOutLargeButton)

    # Rotation
    self.ui.cranialRotationButton.connect('clicked(bool)', self.onCranialRotationButton)
    self.ui.caudalRotationButton.connect('clicked(bool)', self.onCaudalRotationButton)
    self.ui.leftRotationButton.connect('clicked(bool)', self.onLeftRotationButton)
    self.ui.rightRotationButton.connect('clicked(bool)', self.onRightRotationButton)

    # Slider changes

    self.ui.leftRightSlider.connect("valueChanged(double)", self.updateParameterNodeFromGUI)
    self.ui.upDownSlider.connect("valueChanged(double)", self.updateParameterNodeFromGUI)
    self.ui.cranialRotationSlider.connect("valueChanged(double)", self.updateParameterNodeFromGUI)
    self.ui.leftRotationSlider.connect("valueChanged(double)", self.updateParameterNodeFromGUI)

    # Saving
    self.ui.saveDirectoryButton.connect('directorySelected(QString)', self.onSaveDirectoryChanged)
    self.ui.participantIDLineEdit.connect('textChanged(QString)', self.onParticipantIDChanged)
    self.ui.saveButton.connect('clicked(bool)', self.onSaveButton)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()
    self.initializeGUI() # This is an addition to avoid initializing parameter node before connections
    self.updateWidgetsForCurrentVolume()
    self.onResetNeedleButton()

  def initializeGUI(self):
    # initailize the save directory using settings
    settings = slicer.app.userSettings()
    if settings.value(self.logic.RESULTS_SAVE_DIRECTORY_SETTING): # if the settings exists
      self.ui.saveDirectoryButton.directory = settings.value(self.logic.RESULTS_SAVE_DIRECTORY_SETTING)
    # initailize the path to current task using settings
    if settings.value(self.logic.CURRENT_TASK_SETTING): # if the settings exists
      self.ui.taskSelector.setCurrentPath(settings.value(self.logic.CURRENT_TASK_SETTING))

  def setupCustomLayout(self):
    customLayout = \
      """
      <layout type="horizontal">
        <item>
          <view class="vtkMRMLViewNode" singletontag="1">
            <property name="viewLabel" action="default">1</property>
          </view>
        </item>
        <item>
          <view class="vtkMRMLViewNode" singletontag="2" type="secondary">
            <property name="viewlabel" action="default">2</property>
          </view>
        </item>
      </layout>
      """
    # Built-in layout IDs are all below 100, so you can choose any large random number
    # for your custom layout ID.
    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(self.LAYOUT_DUAL3D, customLayout)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Make sure parameter node exists and observed
    self.initializeParameterNode()
    # change to custom double 3D view here
    self.resetViews()
    
  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    if self.parent.isEntered:
      self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.setParameterNode(self.logic.getParameterNode())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update widgets from parameter node

    currentUsVolume = self.ui.usVolumeComboBox.currentNode()
    referencedVolume = self._parameterNode.GetNodeReference(self.logic.CURRENT_US_VOLUME)
    if currentUsVolume != referencedVolume:
      self.ui.usVolumeComboBox.setCurrentNode(referencedVolume)

    currentNeedleTransform = self.ui.needleTransformComboBox.currentNode()
    referencedTransform = self._parameterNode.GetNodeReference(self.logic.NEEDLE_TO_RAS_TRANSFORM)
    if currentNeedleTransform != referencedTransform:
      self.ui.needleTransformComboBox.setCurrentNode(referencedTransform)

    # update the sliders from the parameter node
    self.ui.leftRightSlider.value = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_R))
    self.ui.upDownSlider.value = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_S))
    self.ui.cranialRotationSlider.value = float(self._parameterNode.GetParameter(self.logic.ROTATE_R))
    self.ui.leftRotationSlider.value = float(self._parameterNode.GetParameter(self.logic.ROTATE_S))

    # update participant ID
    self.ui.participantIDLineEdit.text = self._parameterNode.GetParameter(self.logic.PARTICIPANT_ID)

    # Update buttons states and tooltips

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateWidgetsForCurrentVolume(self):
    """
    Update widget parameters that depend on the size and position of current volume.
    """
    usVolume = self._parameterNode.GetNodeReference(self.logic.CURRENT_US_VOLUME)
    if usVolume is None:
      return

    bounds = np.zeros(6)
    usVolume.GetRASBounds(bounds)

    # Update sliders to cover the volumem with extra margins

    self.ui.leftRightSlider.minimum = bounds[0] - self.logic.MOTION_MARGIN
    self.ui.leftRightSlider.maximum = bounds[1] + self.logic.MOTION_MARGIN
    self.ui.upDownSlider.minimum = bounds[4] - self.logic.MOTION_MARGIN
    self.ui.upDownSlider.maximum = bounds[5] + self.logic.MOTION_MARGIN

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    self._parameterNode.SetParameter(self.logic.TRANSLATE_R, str(self.ui.leftRightSlider.value))
    self._parameterNode.SetParameter(self.logic.TRANSLATE_S, str(self.ui.upDownSlider.value))
    self._parameterNode.SetParameter(self.logic.ROTATE_R, str(self.ui.cranialRotationSlider.value))
    self._parameterNode.SetParameter(self.logic.ROTATE_S, str(self.ui.leftRotationSlider.value))
    self.logic.updateTransformFromParameterNode()

    self._parameterNode.EndModify(wasModified)

  def onUsVolumeSelected(self, selectedNode):
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    previousReferencedNode = self._parameterNode.GetNodeReference(self.logic.CURRENT_US_VOLUME)

    if selectedNode is None:
      self._parameterNode.SetNodeReferenceID(self.logic.CURRENT_US_VOLUME, "")
    else:
      self._parameterNode.SetNodeReferenceID(self.logic.CURRENT_US_VOLUME, selectedNode.GetID())

    if previousReferencedNode == selectedNode or selectedNode is None:
      return

    self.updateWidgetsForCurrentVolume()

    # Make sure volume has a volume rendering display node, and display is visible in all 3D views
    volumeRenderingLogic = slicer.modules.volumerendering.logic()
    displayNode = volumeRenderingLogic.GetFirstVolumeRenderingDisplayNode(selectedNode)
    if displayNode is None:
      selectedNode.CreateDefaultDisplayNodes()
      slicer.modules.volumerendering.logic().CreateDefaultVolumeRenderingNodes(selectedNode) 
    displayNode.SetViewNodeIDs([])  # Empty list means all views

    self.resetViews()

  def onNeedleTransformSelected(self, selectedNode):
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    if selectedNode is None:
      self._parameterNode.SetNodeReferenceID(self.logic.NEEDLE_TO_RAS_TRANSFORM, "")
    else:
      self._parameterNode.SetNodeReferenceID(self.logic.NEEDLE_TO_RAS_TRANSFORM, selectedNode.GetID())

    self.logic.updateParameterNodeFromTransform()

    self.logic.updateTransformFromParameterNode()

  # Scene selection
  def onPreviousButton(self):
    self.updateParameterNodeFromGUI()
    self.logic.previousScene()

  def onNextButton(self):
    self.updateParameterNodeFromGUI()
    self.logic.nextScene()

  def onResetNeedleButton(self):
    '''
    This function resets the position and orientation of the needle to default values determined by the current volume size
    '''
    # The slider ranges are set according to the current volume
    # Reset the needle location to the midpont of the slider range
    # Get min and max of the slider range
    minR = self.ui.leftRightSlider.minimum
    maxR = self.ui.leftRightSlider.maximum
    minS = self.ui.upDownSlider.minimum
    maxS = self.ui.upDownSlider.maximum
    # Set the translations in parameter node to midpoints
    self._parameterNode.SetParameter(self.logic.TRANSLATE_R, str(round((maxR + minR) / 2)))
    self._parameterNode.SetParameter(self.logic.TRANSLATE_S, str(round((maxS + minS) / 2)))
    # Set the rotations to 0
    self._parameterNode.SetParameter(self.logic.ROTATE_R, str(90))
    self._parameterNode.SetParameter(self.logic.ROTATE_S, str(0))

    # If there is a volume, make the needle as far back as possible, else make it 0
    usVolume = self._parameterNode.GetNodeReference(self.logic.CURRENT_US_VOLUME)
    if usVolume is None:
      self._parameterNode.SetParameter(self.logic.TRANSLATE_A, str(0))
    else:
      bounds = np.zeros(6)
      usVolume.GetRASBounds(bounds)
      self._parameterNode.SetParameter(self.logic.TRANSLATE_A, str(bounds[2]))

    # update the transform
    self.logic.updateTransformFromParameterNode()

  def resetViews(self):
    '''
    Resets the virtual camera positions
    '''
    layoutManager = slicer.app.layoutManager()
    layoutManager.setLayout(self.LAYOUT_DUAL3D)

    # Setup 3D view 0
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint()
    threeDView.rotateToViewAxis(2)
    viewNode = threeDView.mrmlViewNode()
    viewNode.SetOrientationMarkerType(viewNode.OrientationMarkerTypeHuman)
    viewNode.SetOrientationMarkerSize(1)
    viewNode.SetBoxVisible(False)
    viewNode.SetAxisLabelsVisible(False)

    # Setup 3D view 1
    threeDWidget = layoutManager.threeDWidget(1)
    threeDView = threeDWidget.threeDView()
    threeDView.resetFocalPoint()
    threeDView.rotateToViewAxis(0)
    viewNode = threeDView.mrmlViewNode()
    viewNode.SetOrientationMarkerType(viewNode.OrientationMarkerTypeHuman)
    viewNode.SetOrientationMarkerSize(1)
    viewNode.SetBoxVisible(False)
    viewNode.SetAxisLabelsVisible(False)

  # Tranlation
  def onRightButton(self):
    self.ui.leftRightSlider.value = self.ui.leftRightSlider.value + self.logic.STEP_SIZE_TRANSLATION

  def onLeftButton(self):
    self.ui.leftRightSlider.value = self.ui.leftRightSlider.value - self.logic.STEP_SIZE_TRANSLATION

  def onUpButton(self):
    self.ui.upDownSlider.value = self.ui.upDownSlider.value + self.logic.STEP_SIZE_TRANSLATION

  def onDownButton(self):
    self.ui.upDownSlider.value = self.ui.upDownSlider.value - self.logic.STEP_SIZE_TRANSLATION

  def onInButton(self):
    self.logic.moveNeedleIn(1)

  def onInLargeButton(self):
    self.logic.moveNeedleIn(10)

  def onOutButton(self):
    self.logic.moveNeedleIn(-1)

  def onOutLargeButton(self):
    self.logic.moveNeedleIn(-10)

  # Rotation
  def onCranialRotationButton(self):
    self.ui.cranialRotationSlider.value = self.ui.cranialRotationSlider.value + self.logic.STEP_SIZE_ROTATION

  def onCaudalRotationButton(self):
    self.ui.cranialRotationSlider.value = self.ui.cranialRotationSlider.value - self.logic.STEP_SIZE_ROTATION

  def onLeftRotationButton(self):
    self.ui.leftRotationSlider.value = self.ui.leftRotationSlider.value - self.logic.STEP_SIZE_ROTATION

  def onRightRotationButton(self):
    self.ui.leftRotationSlider.value = self.ui.leftRotationSlider.value + self.logic.STEP_SIZE_ROTATION

  # Saving results
  def onSaveDirectoryChanged(self, directory):
    # update settings with the new directory
    settings = slicer.app.userSettings()
    settings.setValue(self.logic.RESULTS_SAVE_DIRECTORY_SETTING, directory)
    
  def onParticipantIDChanged(self, participantID):
    # update the participant ID in the parameter node
    self._parameterNode.SetParameter(self.logic.PARTICIPANT_ID, participantID)

  def onTaskChanged(self, taskPath):
    # Get the filename from the taskPath without the extension
    taskName = os.path.splitext(os.path.basename(taskPath))[0]
    self._parameterNode.SetParameter(self.logic.TASK_NAME, taskName)
    settings = slicer.app.userSettings()
    settings.setValue(self.logic.CURRENT_TASK_SETTING, taskPath)

  def onSaveButton(self):
    self.logic.saveResults()


#
# SpineGuidanceStudyModuleLogic
#

class SpineGuidanceStudyModuleLogic(ScriptedLoadableModuleLogic):
  CURRENT_US_VOLUME = "CurrentUsVolume"
  MOTION_MARGIN = 100  # Allow needle to go outside image volume by this many mm
  STEP_SIZE_TRANSLATION = 1  # Translation single click in mm
  STEP_SIZE_ROTATION = 1  # Rotation single click in degrees

  NEEDLE_TO_RAS_TRANSFORM = "NeedleToRasTransform"
  NEEDLE_MODEL = "NeedleModel"
  TRANSLATE_R = "TranslateR"
  TRANSLATE_A = "TranslateA"
  TRANSLATE_S = "TranslateS"
  ROTATE_R = "RotateR"
  ROTATE_S = "RotateS"

  RESULTS_SAVE_DIRECTORY_SETTING = 'SpineGuidance/ResultsSaveDirectory'
  PARTICIPANT_ID = "ParticipantID"
  CURRENT_TASK_SETTING = 'SpineGuidance/CurrentTask'
  TASK_NAME = "TaskName"

  def __init__(self):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """
    ScriptedLoadableModuleLogic.__init__(self)
    self.NEEDLE_TRANSFORM = "needle_RAStoNeedle"
    self.NEEDLE_TIP = "needleTip"

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    # Set Translate R
    if not parameterNode.GetParameter(self.TRANSLATE_R):
      parameterNode.SetParameter(self.TRANSLATE_R, "0")
    # Set Translate A
    if not parameterNode.GetParameter(self.TRANSLATE_A):
      parameterNode.SetParameter(self.TRANSLATE_A, "0")
    # Set Translate S
    if not parameterNode.GetParameter(self.TRANSLATE_S):
      parameterNode.SetParameter(self.TRANSLATE_S, "0")
    # Set Rotate R
    if not parameterNode.GetParameter(self.ROTATE_R):
      parameterNode.SetParameter(self.ROTATE_R, "0")
    # Set Rotate S
    if not parameterNode.GetParameter(self.ROTATE_S):
      parameterNode.SetParameter(self.ROTATE_S, "0")
    pass

  def process(self, inputVolume, outputVolume, imageThreshold, invert=False, showResult=True):
    pass

  def setupScene(self):
    parameterNode = self.getParameterNode()

    # NeedleToRasTransform

    # If NeedleToRasTransform is not in the scene, create and add it
    needleToRasTransform = slicer.util.getFirstNodeByName(self.NEEDLE_TO_RAS_TRANSFORM)  # ***
    if needleToRasTransform is None:
      needleToRasTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', self.NEEDLE_TO_RAS_TRANSFORM)
      parameterNode.SetNodeReferenceID(self.NEEDLE_TO_RAS_TRANSFORM, needleToRasTransform.GetID())

    # NeedleModel

    # If NeedleModel is not in the scene, create and add it
    needleModel = slicer.util.getFirstNodeByName(self.NEEDLE_MODEL)
    if needleModel is None:
      createModelsLogic = slicer.modules.createmodels.logic()
      # creates a needle model with 4 arguments: Length, radius, tip radius, and DepthMarkers
      needleModel = createModelsLogic.CreateNeedle(80, 1.0, 2.5, 0)
      needleModel.SetName(self.NEEDLE_MODEL)
      parameterNode.SetNodeReferenceID(self.NEEDLE_MODEL, needleModel.GetID())
    # If not already transformed, add it to the NeedleToRas transform
    needleModelTransform = needleModel.GetParentTransformNode()
    if needleModelTransform is None:
      needleModel.SetAndObserveTransformNodeID(needleToRasTransform.GetID())

    # NeedleTip pointlist

    # If pointList_NeedleTip is not in the scene, create and add it
    pointList_NeedleTip = parameterNode.GetNodeReference(self.NEEDLE_TIP)
    if pointList_NeedleTip == None:
      # Create a point list for the needle tip in reference coordinates
      pointList_NeedleTip = slicer.vtkMRMLMarkupsFiducialNode()
      pointList_NeedleTip.SetName("pointList_NeedleTip")
      slicer.mrmlScene.AddNode(pointList_NeedleTip)
      # Set the role of the point list
      parameterNode.SetNodeReferenceID(self.NEEDLE_TIP, pointList_NeedleTip.GetID())
    # Add a point to the point list
    if pointList_NeedleTip.GetNumberOfControlPoints() == 0:
      pointList_NeedleTip.AddControlPoint(np.array([0, 0, 0]))
      pointList_NeedleTip.SetNthControlPointLabel(0, "origin_Tip")

    pointList_NeedleTip.GetDisplayNode().SetVisibility(False)  # Hide needle tip markup by default

    # If not already transformed, add it to the NeedleToRas transform
    pointList_NeedleTipTransform = pointList_NeedleTip.GetParentTransformNode()
    if pointList_NeedleTipTransform is None:
      pointList_NeedleTip.SetAndObserveTransformNodeID(needleToRasTransform.GetID())

  def previousScene(self):
    pass

  def nextScene(self):
    pass

  def updateTransformFromParameterNode(self):
    """
    Update the transform from the parameter node
    """
    parameterNode = self.getParameterNode()  # Get the parameter node

    # apply the translation and rotation in the world frame: TRANSLATE_R, TRANSLATE_S, ROTATE_R, ROTATE_S

    needleToRasTransform = vtk.vtkTransform()
    needleToRasTransform.Translate(float(parameterNode.GetParameter(self.TRANSLATE_R)),
                                   float(parameterNode.GetParameter(self.TRANSLATE_A)),
                                   float(parameterNode.GetParameter(self.TRANSLATE_S)))
    rotationX = float(parameterNode.GetParameter(self.ROTATE_R)) - 90
    rotationY = float(parameterNode.GetParameter(self.ROTATE_S))

    needleToRasTransform.RotateX(rotationX)  # Start at anterior direction
    needleToRasTransform.RotateY(rotationY)

    # Set the transform to the transform node

    needleToRasTransformNode = parameterNode.GetNodeReference(self.NEEDLE_TO_RAS_TRANSFORM)
    if needleToRasTransformNode is not None:
      needleToRasTransformNode.SetAndObserveTransformToParent(needleToRasTransform)
    else:
      logging.warning("Needle transform not selected yet")

  def updateParameterNodeFromTransform(self):
    """
    Estimate motion parameters from the current transform. This is needed if we want to continue an existing transform
    that has not been selected previously.
    """
    parameterNode = self.getParameterNode()

    needleToRasTransformNode = parameterNode.GetNodeReference(self.NEEDLE_TO_RAS_TRANSFORM)
    if needleToRasTransformNode is None:
      return

    needleToRasTransform = needleToRasTransformNode.GetTransformToParent()

    needleToRasTranslation = np.array(needleToRasTransform.GetPosition())
    parameterNode.SetParameter(self.TRANSLATE_R, str(needleToRasTranslation[0]))
    parameterNode.SetParameter(self.TRANSLATE_A, str(needleToRasTranslation[1]))
    parameterNode.SetParameter(self.TRANSLATE_S, str(needleToRasTranslation[2]))

    #todo: This does not correctly preserve orientation. We need to figure out how to get rotation values to be compatible
    # with updateTransformFromParameterNode()

    needleToRasOrientation = np.array(needleToRasTransform.GetOrientation())
    parameterNode.SetParameter(self.ROTATE_R, str(needleToRasOrientation[0] + 90))
    parameterNode.SetParameter(self.ROTATE_S, str(needleToRasOrientation[1]))

  def moveNeedleIn(self, distance):
    # Get the parameter node
    parameterNode = self.getParameterNode()
    # Get the transform node from the parameter node
    needleToRasTransformNode = parameterNode.GetNodeReference(self.NEEDLE_TO_RAS_TRANSFORM)
    # Get the transform from the transform node
    needleToRasTransform = needleToRasTransformNode.GetTransformToParent()
    # Find distance in terms of R and S
    Translation_Needle = [0, 0, distance]
    # Rotate Translation_Needle to the parent frame
    Translation_RAS = needleToRasTransform.TransformVector(Translation_Needle)
    # Add Translation_RAS to the current translation
    parameterNode.SetParameter(self.TRANSLATE_R, str(float(parameterNode.GetParameter(self.TRANSLATE_R)) + Translation_RAS[0]))
    parameterNode.SetParameter(self.TRANSLATE_A, str(float(parameterNode.GetParameter(self.TRANSLATE_A)) + Translation_RAS[1]))
    parameterNode.SetParameter(self.TRANSLATE_S, str(float(parameterNode.GetParameter(self.TRANSLATE_S)) + Translation_RAS[2]))
    # Update transform from Parameter Node
    self.updateTransformFromParameterNode()

  def saveResults(self):
    ''' 
    Save the results to a file:
    - NeedleToRasTransform
    Save in format:
    NeedleToRas_TaskName_ParticipantID.h5
    '''
    # Get the parameter node
    parameterNode = self.getParameterNode()

    # Get the NeedleToRasTransform maxtrix node to save
    needleToRasTransformNode = parameterNode.GetNodeReference(self.NEEDLE_TO_RAS_TRANSFORM)
    
    # Format the name of the file
    # Get the task name
    taskName = parameterNode.GetParameter(self.TASK_NAME)
    # Get the participant ID
    participantID = parameterNode.GetParameter(self.PARTICIPANT_ID)
    # Get the transform name
    transformName = needleToRasTransformNode.GetName()
    # Get the file name
    fileName = transformName + "_" + taskName + "_" + participantID + ".h5"
    # Get the Save Directory from slicer settings
    settings = slicer.app.userSettings()
    saveDirectory = settings.value(self.RESULTS_SAVE_DIRECTORY_SETTING)

    # Save the NeedleToRasTransform to saveDirectory with fileName
    slicer.util.saveNode(needleToRasTransformNode, os.path.join(saveDirectory, fileName))

#
# SpineGuidanceStudyModuleTest
#

class SpineGuidanceStudyModuleTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear()

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SpineGuidanceStudyModule1()

  def test_SpineGuidanceStudyModule1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    # Get/create input data

    import SampleData
    registerSampleData()
    inputVolume = SampleData.downloadSample('SpineGuidanceStudyModule1')
    self.delayDisplay('Loaded test data set')

    inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    self.assertEqual(inputScalarRange[0], 0)
    self.assertEqual(inputScalarRange[1], 695)

    # Test the module logic

    logic = SpineGuidanceStudyModuleLogic()

    # todo: add logic test code here

    self.delayDisplay('Test passed')
