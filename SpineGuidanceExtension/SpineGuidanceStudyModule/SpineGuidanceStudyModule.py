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
        self.parent.title = "SpineGuidanceStudyModule"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["Examples"]  # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["David Morton (Perk Lab)"]
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """
        This is an example of scripted loadable module bundled in an extension.
        See more information in <a href="https://github.com/organization/projectname#SpineGuidanceStudyModule">module documentation</a>.
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

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
        # (in the selected parameter node).
        self.ui.sceneSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

        # Scene selection
        self.ui.previousButton.connect('clicked(bool)', self.onPreviousButton)
        self.ui.nextButton.connect('clicked(bool)', self.onNextButton)

        # Translation
        self.ui.leftButton.connect('clicked(bool)', self.onLeftButton)
        self.ui.rightButton.connect('clicked(bool)', self.onRightButton)
        self.ui.leftRightSlider.connect("valueChanged(double)", self.onLeftRightSlider)
        self.ui.upButton.connect('clicked(bool)', self.onUpButton)
        self.ui.downButton.connect('clicked(bool)', self.onDownButton)
        self.ui.upDownSlider.connect("valueChanged(double)", self.onUpDownSlider)
        self.ui.inButton.connect('clicked(bool)', self.onInButton)
        self.ui.outButton.connect('clicked(bool)', self.onOutButton)
        self.ui.inOutSlider.connect("valueChanged(double)", self.onInOutSlider)

        # Rotation
        self.ui.cranialRotationButton.connect('clicked(bool)', self.onCranialRotationButton)
        self.ui.caudalRotationButton.connect('clicked(bool)', self.onCaudalRotationButton)
        self.ui.cranialRotationSlider.connect("valueChanged(double)", self.onCranialRotationSlider)
        self.ui.leftRotationButton.connect('clicked(bool)', self.onLeftRotationButton)
        self.ui.rightRotationButton.connect('clicked(bool)', self.onRightRotationButton)
        self.ui.leftRotationSlider.connect("valueChanged(double)", self.onLeftRotationSlider)



        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()
        # Setup the scene
        self.initializeScene()       

    def initializeScene(self):
        # NeedleToRasTransform

        # If NeedleToRasTransform is not in the scene, create and add it
        needleToRasTransform = slicer.util.getFirstNodeByName(self.logic.NEEDLE_TO_RAS_TRANSFORM) # ***
        if needleToRasTransform is None:
            needleToRasTransform = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', self.logic.NEEDLE_TO_RAS_TRANSFORM)
            # Add it to parameter node
            self._parameterNode.SetNodeReferenceID(self.logic.NEEDLE_TO_RAS_TRANSFORM, needleToRasTransform.GetID())

        # NeedleModel

        # If NeedleModel is not in the scene, create and add it
        needleModel = slicer.util.getFirstNodeByName(self.logic.NEEDLE_MODEL)
        if needleModel is None:
            createModelsLogic = slicer.modules.createmodels.logic()
            # creates a needle model with 4 arguments: Length, radius, tip radius, and DepthMarkers
            needleModel = createModelsLogic.CreateNeedle(80,1.0,2.5, 0)
            needleModel.SetName(self.logic.NEEDLE_MODEL)
            # Add it to parameter node
            self._parameterNode.SetNodeReferenceID(self.logic.NEEDLE_MODEL, needleModel.GetID())
        # If not already transformed, add it to the NeedleToRas transform
        needleModelTransform = needleModel.GetParentTransformNode()
        if needleModelTransform is None:
            needleModel.SetAndObserveTransformNodeID(needleToRasTransform.GetID())

        # NeedleTip pointlist
    
        # If pointList_NeedleTip is not in the scene, create and add it
        pointList_NeedleTip = self._parameterNode.GetNodeReference(self.logic.NEEDLE_TIP)
        if pointList_NeedleTip == None:
            # Create a point list for the needle tip in reference coordinates
            pointList_NeedleTip = slicer.vtkMRMLMarkupsFiducialNode()
            pointList_NeedleTip.SetName("pointList_NeedleTip")
            slicer.mrmlScene.AddNode(pointList_NeedleTip)
            # Set the role of the point list
            self._parameterNode.SetNodeReferenceID(self.logic.NEEDLE_TIP, pointList_NeedleTip.GetID())
        # Add a point to the point list
        if pointList_NeedleTip.GetNumberOfControlPoints() == 0:
            pointList_NeedleTip.AddControlPoint(np.array([0, 0, 0]))
            pointList_NeedleTip.SetNthControlPointLabel(0, "origin_Tip")
        # If not already transformed, add it to the NeedleToRas transform
        pointList_NeedleTipTransform = pointList_NeedleTip.GetParentTransformNode()
        if pointList_NeedleTipTransform is None:
            pointList_NeedleTip.SetAndObserveTransformNodeID(needleToRasTransform.GetID())
        
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
        # Set default parameters
        print("initializeParameterNode")
        self.updateGUIFromParameterNode()
         
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
        self.initializeScene()

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        self._updatingGUIFromParameterNode = True

        # update the sliders from the parameter node
        self.ui.leftRightSlider.value = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_R))
        self.ui.upDownSlider.value = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_S))
        self.ui.inOutSlider.value = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_A))
        self.ui.cranialRotationSlider.value = float(self._parameterNode.GetParameter(self.logic.ROTATE_R))
        self.ui.leftRotationSlider.value = float(self._parameterNode.GetParameter(self.logic.ROTATE_S))

        # Update buttons states and tooltips


        # All the GUI updates are done
        self._updatingGUIFromParameterNode = False

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
        self._parameterNode.SetParameter(self.logic.TRANSLATE_A, str(self.ui.inOutSlider.value))
        self._parameterNode.SetParameter(self.logic.ROTATE_R, str(self.ui.cranialRotationSlider.value))
        self._parameterNode.SetParameter(self.logic.ROTATE_S, str(self.ui.leftRotationSlider.value))


        self._parameterNode.EndModify(wasModified)

    # Scene selection
    def onPreviousButton(self):
        self.updateParameterNodeFromGUI()
        self.logic.previousScene()
        
    def onNextButton(self):
        self.updateParameterNodeFromGUI()
        self.logic.nextScene()

    # Tranlation
    def onRightButton(self):
        # Add 1 to Right Translation
        currentTr = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_R))
        self._parameterNode.SetParameter(self.logic.TRANSLATE_R, str(currentTr + 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()

    def onLeftButton(self):
        # Subtract 1 from Right Translation
        currentTr = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_R))
        self._parameterNode.SetParameter(self.logic.TRANSLATE_R, str(currentTr - 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()

    def onLeftRightSlider(self):
        self.updateParameterNodeFromGUI()
        self.logic.updateTransformFromParameterNode()

    def onUpButton(self):
        # Add 1 to Superior Translation 
        currentTs = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_S))
        self._parameterNode.SetParameter(self.logic.TRANSLATE_S, str(currentTs + 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()

    def onDownButton(self):
        # Subtract 1 from Superior Translation
        currentTs = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_S))
        self._parameterNode.SetParameter(self.logic.TRANSLATE_S, str(currentTs - 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()

    def onUpDownSlider(self):
        self.updateParameterNodeFromGUI()
        self.logic.updateTransformFromParameterNode()

    def onInButton(self):
        # Add 1 to Anterior Translation
        currentTa = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_A))
        self._parameterNode.SetParameter(self.logic.TRANSLATE_A, str(currentTa + 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()
  
    def onOutButton(self):
        # Subtract 1 from Anterior Translation
        currentTa = float(self._parameterNode.GetParameter(self.logic.TRANSLATE_A))
        self._parameterNode.SetParameter(self.logic.TRANSLATE_A, str(currentTa - 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()
 
    def onInOutSlider(self):
        self.updateParameterNodeFromGUI()
        self.logic.updateTransformFromParameterNode()

    
    # Rotation
    def onCranialRotationButton(self):
        # Add 1 degree to Rotation R 
        currentRr = float(self._parameterNode.GetParameter(self.logic.ROTATE_R))
        self._parameterNode.SetParameter(self.logic.ROTATE_R, str(currentRr + 1))
        self.updateGUIFromParameterNode()

    def onCaudalRotationButton(self):
        # Subtract 1 degree from Rotation R
        currentRr = float(self._parameterNode.GetParameter(self.logic.ROTATE_R))
        self._parameterNode.SetParameter(self.logic.ROTATE_R, str(currentRr - 1))
        self.updateGUIFromParameterNode()
        
    def onCranialRotationSlider(self):
        self.updateParameterNodeFromGUI()
        # Print the rotation parameters 
        print('Rotation R: ' + self._parameterNode.GetParameter(self.logic.ROTATE_R))
        self.logic.updateTransformFromParameterNode()
    
    def onLeftRotationButton(self):
        # Add 1 degree to Rotation S
        currentRs = float(self._parameterNode.GetParameter(self.logic.ROTATE_S))
        self._parameterNode.SetParameter(self.logic.ROTATE_S, str(currentRs + 1))
        # print Rotation S
        print(self._parameterNode.GetParameter(self.logic.ROTATE_S))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()

    def onRightRotationButton(self):
        # Subtract 1 degree from Rotation S
        currentRs = float(self._parameterNode.GetParameter(self.logic.ROTATE_S))
        self._parameterNode.SetParameter(self.logic.ROTATE_S, str(currentRs - 1))
        self.updateGUIFromParameterNode()
        self.logic.updateTransformFromParameterNode()

    def onLeftRotationSlider(self):
        self.updateParameterNodeFromGUI()
        print('Rotation S: ' + self._parameterNode.GetParameter(self.logic.ROTATE_S))
        self.logic.updateTransformFromParameterNode()

    

    


#
# SpineGuidanceStudyModuleLogic
#

class SpineGuidanceStudyModuleLogic(ScriptedLoadableModuleLogic):

    NEEDLE_TO_RAS_TRANSFORM = "NeedleToRasTransform"
    NEEDLE_MODEL = "NeedleModel"
    TRANSLATE_R = "TranslateR"
    TRANSLATE_A = "TranslateA"
    TRANSLATE_S = "TranslateS"
    ROTATE_R = "RotateR"
    ROTATE_S = "RotateS"
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
        pass

    def process(self, inputVolume, outputVolume, imageThreshold, invert=False, showResult=True):
        pass

    def previousScene(self):
        pass

    def nextScene(self):
        pass

    def updateTransformFromParameterNode(self):
        """
        Update the transform from the parameter node

        """
        # Get the parameter node
        parameterNode = self.getParameterNode()
        # Get the transform node from the parameter node
        needleToRasTransformNode = parameterNode.GetNodeReference(self.NEEDLE_TO_RAS_TRANSFORM)
        # create a new transform from the translation components in the parameter node
        needleToRasTransform = vtk.vtkTransform()
        needleToRasTransform.Translate(-float(parameterNode.GetParameter(self.TRANSLATE_R)),
                                        float(parameterNode.GetParameter(self.TRANSLATE_A)),
                                        float(parameterNode.GetParameter(self.TRANSLATE_S)))
        needleToRasTransform.RotateX(float(parameterNode.GetParameter(self.ROTATE_R)))
        needleToRasTransform.RotateY(float(parameterNode.GetParameter(self.ROTATE_S)))
        # Set the transform to the transform node
        needleToRasTransformNode.SetAndObserveTransformToParent(needleToRasTransform)



    def moveLeft(self):
        parameterNode = self.getParameterNode() 
        # Translate the needle by 1 mm
        # add one to the current Tr
        currentTr = float(parameterNode.GetParameter(self.TRANSLATE_R))
        parameterNode.SetParameter(self.TRANSLATE_R, str(currentTr + 1))
        print(parameterNode.GetParameter(self.TRANSLATE_R))

        # Get the NeedleToRasTransform

        needleToRasNode = parameterNode.GetNodeReference(self.NEEDLE_TO_RAS_TRANSFORM)
        needleToRasMatrix = vtk.vtkMatrix4x4()
        needleToRasNode.GetMatrixTransformToParent(needleToRasMatrix)

    def moveLeftRight(self):
        '''This function updates the R translation in the parameter node with the slider value'''
        # Print the slider value
        parameterNode = self.getParameterNode()
        print("LeftRightSlider: ", parameterNode.GetParameter(self.TRANSLATE_R))

    def moveRight(self):
        pass

    def rotateNeedle(self):
        self.setupLists()
        # Get the tip of the needle
        centerOfRotationMarkupsNode = self.getParameterNode().GetNodeReference(self.NEEDLE_TIP)
        # This transform can be  edited in Transforms module
        rotationTransformNode  = self.getParameterNode().GetNodeReference(self.NEEDLE_TRANSFORM)
        # This transform has to be applied to the image, model, etc.
        finalTransformNode = slicer.util.getNode('LinearTransform_1')

        
        rotationMatrix = vtk.vtkMatrix4x4()
        rotationTransformNode.GetMatrixTransformToParent(rotationMatrix)
        rotationCenterPointCoord = [0.0, 0.0, 0.0]
        centerOfRotationMarkupsNode.GetNthControlPointPositionWorld(0, rotationCenterPointCoord)
        print("rotationCenterPointCoord: ", rotationCenterPointCoord)
        finalTransform = vtk.vtkTransform()
        finalTransform.Translate(rotationCenterPointCoord)
        finalTransform.Concatenate(rotationMatrix)
        finalTransform.Translate(-rotationCenterPointCoord[0], -rotationCenterPointCoord[1], -rotationCenterPointCoord[2])
        finalTransformNode.SetAndObserveMatrixTransformToParent(finalTransform.GetMatrix())
        pass

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

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = SpineGuidanceStudyModuleLogic()

        # Test algorithm with non-inverted threshold
        logic.process(inputVolume, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(inputVolume, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        self.delayDisplay('Test passed')
