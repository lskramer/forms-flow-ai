import React, { useState, useEffect } from "react";
import Grid from "@material-ui/core/Grid";
import CardContent from "@material-ui/core/CardContent";
import Card from "@material-ui/core/Card";
import Select from "react-dropdown-select";
import EditModel from "./ModelEditorHook";
import { useSelector, useDispatch } from "react-redux";
import {
  setWorkflowAssociation,
  setProcessDiagramXML,
} from "../../actions/processActions";
import { useTranslation } from "react-i18next";
import { listProcess } from "../../apiManager/services/formatterService";
import "./Modeller.scss";

import {
  fetchAllBpmProcesses,
} from "../../apiManager/services/processServices";

import Button from "react-bootstrap/Button";

import { createNewProcess } from "./helpers/helper";

export default React.memo(() => {
    const { t } = useTranslation();
    const dispatch = useDispatch();
    const process = useSelector((state) => state.process.processList);
    const processList = listProcess(process);
    const workflow = useSelector((state) => state.process.workflowAssociated);
    const [defaultProcessInfo, setDefaultProcessInfo] = useState(createNewProcess());
    const [showModeller, setShowModeller] = useState(false);
    
    // Populate workflows in dropdown on page load and show default workflow
    useEffect(() => {
      dispatch(fetchAllBpmProcesses());
    }, []);

    const handleListChange = (item) => {
      setShowModeller(true);
      dispatch(setWorkflowAssociation(item[0]));
      // Clear the filename after the "Choose File" input button
      if (item[0] !== defaultProcessInfo.defaultWorkflow){
        document.getElementById("inputWorkflow").value = "";
      }
    };

    const handleFile = (e) => {
      const content = e.target.result;
      dispatch(setProcessDiagramXML(content));
      dispatch(setWorkflowAssociation(defaultProcessInfo.defaultWorkflow));
      setShowModeller(true);
    };
    
    const handleChangeFile = (file) => {
      let fileData = new FileReader();
      fileData.onloadend = handleFile;
      fileData.readAsText(file);
      setShowModeller(true);
    };
    
    const handleCreateNew = () => {
      const newProcess = createNewProcess();
      setDefaultProcessInfo(newProcess);
      dispatch(setProcessDiagramXML(newProcess.defaultBlankProcessXML));
      dispatch(setWorkflowAssociation(newProcess.defaultWorkflow));
      document.getElementById("inputWorkflow").value = "";
      setShowModeller(true);
    };
    
    return (
      <div className="container" id="main">

        <div className="flex-container">
          <div className="flex-item-left">
            <div style={{ display: "flex" }}>
              <h3 className="task-head" style={{ marginTop: "3px" }}>
                <i className="fa fa-cogs" aria-hidden="true" />
              </h3>
              <h3 className="task-head">
                {" "}
                <span className="forms-text" style={{ marginLeft: "1px" }}>
                  {t("Processes")}
                </span>
              </h3>
            </div>
          </div>
        </div>

        <Grid
          container
          direction="row"
          justify="flex-start"
          alignItems="baseline"
        >
          <Grid item xs={12} sm={12}>
            <Card variant="outlined" className="card-overflow">
              <CardContent>
                <Grid item xs={12} sm={6}>
                  <span className="fontsize-16">
                    {t("Please select an existing workflow.")}
                  </span>
                  <Select
                    dropdownHeight="100px"
                    options={processList}
                    onChange={handleListChange}
                    values={
                      processList.length && workflow?.value && showModeller ? [workflow] : []
                    }
                  />
                </Grid>

                <div className="create-import-container">

                  <span className="fontsize-16">
                    {t("Or create new workflow or import a workflow from a local directory.")}
                  </span>

                  <div className="create-import-btns-container">

                    <Button className="btn-create-new" onClick={() => handleCreateNew()}>Create New</Button>

                    <span className="fontsize-16 or-txt">
                    {t(" ")}
                    </span>
                    
                    <input 
                        id="inputWorkflow"
                        type="file" 
                        accept=".bpmn" 
                        onChange={e => handleChangeFile(e.target.files[0])} 
                      />

                  </div>
                </div>

                {(processList.length && workflow?.value) && showModeller ? (
                  <div>
                    <EditModel
                      processKey={workflow?.value}
                      tenant={workflow?.tenant}
                      defaultProcessInfo={defaultProcessInfo}
                    />
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </Grid>
        </Grid >
      </div>
    );
  }
);

